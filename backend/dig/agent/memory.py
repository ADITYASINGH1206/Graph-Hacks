"""Short-term and cross-session memory graph in FalkorDB (mem_<user_id>)."""

import datetime
import logging
import uuid
from typing import Any

from dig.agent.tools import registry
from dig.graph.client import get_graph
from dig.graph.models import GraphElements

logger = logging.getLogger(__name__)


def get_memory_graph(user_id: str) -> Any:
    """Return the dedicated FalkorDB memory graph for a user."""
    safe_uid = "".join(c if c.isalnum() else "_" for c in user_id)
    return get_graph(f"mem_{safe_uid}")


def ensure_memory_schema(graph: Any) -> None:
    """Ensure indexes exist on memory graph."""
    try:
        graph.query("CREATE INDEX FOR (u:User) ON (u.id)")
        graph.query("CREATE INDEX FOR (s:Session) ON (s.id)")
        graph.query("CREATE INDEX FOR (q:Question) ON (q.id)")
        graph.query("CREATE INDEX FOR (f:Finding) ON (f.id)")
    except Exception:
        pass


def record_finding(
    user_id: str,
    session_id: str,
    question_text: str,
    summary: str,
    decision_ids: list[str],
) -> None:
    """Persist session question and finding to user memory graph."""
    try:
        g = get_memory_graph(user_id)
        ensure_memory_schema(g)

        now_iso = datetime.datetime.now(datetime.UTC).isoformat()
        q_id = f"q_{uuid.uuid4().hex[:8]}"
        f_id = f"f_{uuid.uuid4().hex[:8]}"

        cypher = """
        MERGE (u:User {id: $user_id})
        MERGE (s:Session {id: $session_id})
          ON CREATE SET s.started_at = $ts
        MERGE (u)-[:HAD]->(s)
        CREATE (q:Question {id: $q_id, text: $q_text, ts: $ts})
        CREATE (f:Finding {id: $f_id, summary: $summary, decision_ids: $decision_ids, ts: $ts})
        CREATE (s)-[:ASKED]->(q)
        CREATE (q)-[:PRODUCED]->(f)
        """
        g.query(
            cypher,
            params={
                "user_id": user_id,
                "session_id": session_id,
                "ts": now_iso,
                "q_id": q_id,
                "q_text": question_text,
                "f_id": f_id,
                "summary": summary,
                "decision_ids": decision_ids,
            },
        )
    except Exception as exc:
        logger.warning("Could not record finding to memory graph for %s: %s", user_id, exc)


def recall_findings(
    user_id: str,
    topic: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Retrieve up to limit relevant past findings for a user."""
    findings: list[dict[str, Any]] = []
    try:
        g = get_memory_graph(user_id)
        cypher = """
        MATCH (u:User {id: $user_id})-[:HAD]->(s:Session)-[:ASKED]->(q:Question)-[:PRODUCED]->(f:Finding)
        WHERE f.summary CONTAINS $topic OR q.text CONTAINS $topic
        RETURN f.id, f.summary, f.decision_ids, f.ts
        ORDER BY f.ts DESC LIMIT $limit
        """
        res = g.query(cypher, params={"user_id": user_id, "topic": topic, "limit": limit})
        if res.result_set:
            for row in res.result_set:
                findings.append(
                    {
                        "id": row[0],
                        "summary": row[1],
                        "decision_ids": row[2] or [],
                        "ts": str(row[3]),
                    }
                )
        if not findings:
            # Fallback to most recent findings if exact topic doesn't match
            fallback_cypher = """
            MATCH (u:User {id: $user_id})-[:HAD]->(s:Session)-[:ASKED]->(q:Question)-[:PRODUCED]->(f:Finding)
            RETURN f.id, f.summary, f.decision_ids, f.ts
            ORDER BY f.ts DESC LIMIT $limit
            """
            res_fb = g.query(fallback_cypher, params={"user_id": user_id, "limit": limit})
            if res_fb.result_set:
                for row in res_fb.result_set:
                    findings.append(
                        {
                            "id": row[0],
                            "summary": row[1],
                            "decision_ids": row[2] or [],
                            "ts": str(row[3]),
                        }
                    )
    except Exception as exc:
        logger.warning("Memory recall failed for %s: %s", user_id, exc)

    return findings


def pin_decision(
    user_id: str,
    decision_id: str,
    note: str = "",
) -> dict[str, Any]:
    """Pin a decision to user memory graph with an optional note."""
    try:
        g = get_memory_graph(user_id)
        ensure_memory_schema(g)
        now_iso = datetime.datetime.now(datetime.UTC).isoformat()
        pin_id = f"pin_{uuid.uuid4().hex[:8]}"
        cypher = """
        MERGE (u:User {id: $user_id})
        CREATE (p:Pin {id: $pin_id, decision_id: $decision_id, note: $note, ts: $ts})
        CREATE (u)-[:PINNED]->(p)
        """
        g.query(
            cypher,
            params={
                "user_id": user_id,
                "pin_id": pin_id,
                "decision_id": decision_id,
                "note": note,
                "ts": now_iso,
            },
        )
        return {"status": "pinned", "pin_id": pin_id, "decision_id": decision_id}
    except Exception as exc:
        logger.warning("Pin decision failed: %s", exc)
        return {"status": "error", "message": str(exc)}


@registry.register(
    name="recall",
    description="Recall past findings and answered questions from this user's cross-session memory.",
)
def tool_recall(
    topic: str,
    user_id: str = "anonymous",
    limit: int = 3,
    graph: Any | None = None,
) -> dict[str, Any]:
    findings = recall_findings(user_id=user_id, topic=topic, limit=limit)
    return {
        "data": findings,
        "graph_elements": GraphElements().model_dump(),
        "summary": f"Recalled {len(findings)} past findings for topic '{topic}'.",
    }


@registry.register(
    name="pin",
    description="Pin a critical decision to user memory with an optional note for future reference.",
)
def tool_pin(
    decision_id: str,
    note: str = "",
    user_id: str = "anonymous",
    graph: Any | None = None,
) -> dict[str, Any]:
    res = pin_decision(user_id=user_id, decision_id=decision_id, note=note)
    return {
        "data": res,
        "graph_elements": GraphElements().model_dump(),
        "summary": f"Pinned decision {decision_id} with note '{note}'.",
    }
