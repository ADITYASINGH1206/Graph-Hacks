"""Expertise scoring: computes KNOWS edges for (Person, Module) with exponential recency decay."""

import logging
import math
from datetime import UTC, datetime
from typing import Any

from dig.graph.client import get_graph
from dig.graph.loader import chunk_list

logger = logging.getLogger(__name__)


def parse_timestamp(ts_str: str | None) -> datetime:
    """Parse ISO timestamp string to timezone-aware UTC datetime."""
    if not ts_str:
        return datetime(2020, 1, 1, tzinfo=UTC)
    clean = ts_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except Exception:
        return datetime(2020, 1, 1, tzinfo=UTC)


def compute_and_write_expertise(
    graph: Any | None = None,
    batch_size: int = 500,
) -> dict[str, Any]:
    """Compute (Person, Module) expertise scores with decay and write KNOWS edges."""
    if graph is None:
        graph = get_graph()

    logger.info("Computing expertise scores across Persons and Modules...")
    now = datetime.now(UTC)

    # Activity collectors: (login, module) -> stats
    expertise_map: dict[tuple[str, str], dict[str, Any]] = {}

    def record_activity(
        login: str,
        module: str,
        ts_str: str | None,
        weight: float,
        act_type: str,
    ) -> None:
        key = (login, module)
        if key not in expertise_map:
            expertise_map[key] = {
                "login": login,
                "module": module,
                "score": 0.0,
                "authored": 0,
                "reviewed": 0,
                "commented": 0,
                "last_active": ts_str or "",
            }

        data = expertise_map[key]
        dt = parse_timestamp(ts_str)
        age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
        decay = math.exp(-age_days / 365.0)
        data["score"] += weight * decay

        if act_type == "authored":
            data["authored"] += 1
        elif act_type == "reviewed":
            data["reviewed"] += 1
        elif act_type == "commented":
            data["commented"] += 1

        if ts_str and (not data["last_active"] or ts_str > data["last_active"]):
            data["last_active"] = ts_str

    # 1. Authored merged PRs touching files in module (weight 3.0)
    q_auth = """
    MATCH (p:Person)-[:AUTHORED]->(pr:PullRequest {merged: true})-[:TOUCHES]->(:File)-[:IN_MODULE]->(m:Module)
    WHERE p.is_bot = false
    RETURN DISTINCT p.login, m.name, pr.merged_at
    """
    for row in graph.query(q_auth).result_set:
        record_activity(row[0], row[1], row[2], 3.0, "authored")

    # 2. Reviews on PRs touching files in module (weight 2.0)
    q_rev = """
    MATCH (p:Person)-[:REVIEWED]->(pr:PullRequest)-[:TOUCHES]->(:File)-[:IN_MODULE]->(m:Module)
    WHERE p.is_bot = false
    RETURN DISTINCT p.login, m.name, pr.updated_at
    """
    for row in graph.query(q_rev).result_set:
        record_activity(row[0], row[1], row[2], 2.0, "reviewed")

    # 3. Comments on PRs/Issues touching files in module (weight 1.0)
    q_comm = """
    MATCH (p:Person)-[:COMMENTED_ON]->(pr:PullRequest)-[:TOUCHES]->(:File)-[:IN_MODULE]->(m:Module)
    WHERE p.is_bot = false
    RETURN DISTINCT p.login, m.name, pr.updated_at
    """
    for row in graph.query(q_comm).result_set:
        record_activity(row[0], row[1], row[2], 1.0, "commented")

    # Round scores
    records = list(expertise_map.values())
    for r in records:
        r["score"] = round(r["score"], 2)

    logger.info("Writing %s KNOWS expertise edges into FalkorDB...", len(records))

    # Batch UNWIND write
    for chunk in chunk_list(records, batch_size):
        cypher = """
        UNWIND $batch AS row
        MATCH (p:Person {login: row.login}), (m:Module {name: row.module})
        MERGE (p)-[k:KNOWS]->(m)
        SET k.score = row.score, k.authored = row.authored,
            k.reviewed = row.reviewed, k.commented = row.commented,
            k.last_active = row.last_active
        """
        graph.query(cypher, params={"batch": chunk})

    # Query top people per module for report
    top_per_module: dict[str, list[dict[str, Any]]] = {}
    sample_modules = ["flask/app", "flask/sansio", "flask/json", "flask/helpers"]
    for mod in sample_modules:
        res = graph.query(
            """
            MATCH (p:Person)-[k:KNOWS]->(m:Module {name: $mod})
            RETURN p.login, k.score, k.authored, k.reviewed, k.commented
            ORDER BY k.score DESC LIMIT 5
            """,
            params={"mod": mod},
        )
        if res.result_set:
            top_per_module[mod] = [
                {
                    "login": r[0],
                    "score": r[1],
                    "authored": r[2],
                    "reviewed": r[3],
                    "commented": r[4],
                }
                for r in res.result_set
            ]

    return {
        "knows_edges": len(records),
        "top_per_module": top_per_module,
    }
