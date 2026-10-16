"""Decision linking: classifies relations between decision pairs (SUPERSEDES, REVERSES, DEPENDS_ON, CONFLICTS_WITH)."""

import asyncio
import hashlib
import json
import logging
import re
from typing import Any

from dig.config import settings
from dig.graph.client import get_graph
from dig.ingest.cache import BASE_DATA_DIR

logger = logging.getLogger(__name__)

CACHE_DIR = BASE_DATA_DIR / "cache" / "link"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

REVERT_REGEX = re.compile(
    r"(?i)\brevert(?:s|ed)?\s+(?:(?:to|commit|pr|pull request|issue)?\s*)?#?(\d+)"
)

LINK_SYSTEM_PROMPT = """You classify the semantic relationship between two engineering decisions from the same software project.

Relationships:
- supersedes: The newer decision updates, replaces, or broadens the older decision.
- reverses: The newer decision undoes, cancels, or restores what the older decision changed.
- depends_on: The newer decision requires or builds on the older decision.
- conflicts_with: The newer decision directly contradicts the older active decision.
- none: No direct engineering dependency or conflict exists.

Output JSON only with fields:
{"relation": "supersedes|reverses|depends_on|conflicts_with|none", "confidence": 0.0-1.0, "reason": "brief rationale"}
"""

LINK_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "relation": {
            "type": "string",
            "enum": ["supersedes", "reverses", "depends_on", "conflicts_with", "none"],
        },
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["relation", "confidence", "reason"],
}


def find_candidate_pairs(graph: Any, max_pairs: int = 600) -> list[dict[str, Any]]:
    """Generate candidate pairs of decisions based on shared modules, concepts, or references."""
    cypher = """
    MATCH (d1:Decision), (d2:Decision)
    WHERE d1.id < d2.id
    OPTIONAL MATCH (d1)-[:AFFECTS]->(m:Module)<-[:AFFECTS]-(d2)
    OPTIONAL MATCH (d1)-[:AFFECTS]->(c:Concept)<-[:AFFECTS]-(d2)
    OPTIONAL MATCH (d1)-[:DECIDED_IN]->(s1)-[:REFERENCES|CLOSES]-(s2)<-[:DECIDED_IN]-(d2)
    WITH d1, d2,
         count(DISTINCT m) AS module_overlap,
         count(DISTINCT c) AS concept_overlap,
         count(DISTINCT s1) AS ref_overlap
    WHERE (module_overlap + concept_overlap + ref_overlap) > 0
    RETURN d1, d2, (module_overlap * 2 + concept_overlap * 2 + ref_overlap * 3) AS weight
    ORDER BY weight DESC LIMIT $limit
    """
    res = graph.query(cypher, params={"limit": max_pairs})
    candidates: list[dict[str, Any]] = []
    if res.result_set:
        for row in res.result_set:
            d1_node, d2_node, weight = row[0], row[1], row[2]
            d1 = dict(d1_node.properties)
            d2 = dict(d2_node.properties)

            # Order chronologically: older first, newer second
            t1 = d1.get("decided_at") or ""
            t2 = d2.get("decided_at") or ""
            if t1 > t2:
                older, newer = d2, d1
            else:
                older, newer = d1, d2

            candidates.append({"older": older, "newer": newer, "weight": weight})

    return candidates


def detect_explicit_revert(newer: dict[str, Any], older: dict[str, Any]) -> dict[str, Any] | None:
    """Detect explicit revert cues from pull request titles or summaries."""
    newer_title = newer.get("title", "")
    newer_summary = newer.get("summary", "")
    older_num = older.get("source_number")

    text = f"{newer_title} {newer_summary}"
    match = REVERT_REGEX.search(text)
    if match:
        ref_num = int(match.group(1)) if match.group(1) else None
        if ref_num and older_num and ref_num == int(older_num):
            return {
                "relation": "reverses",
                "confidence": 1.0,
                "reason": f"Explicit revert in PR title/summary referencing #{ref_num}",
            }
        elif "revert" in newer_title.lower() and older.get("type") in (
            "deprecation",
            "adoption",
            "design",
        ):
            return {
                "relation": "reverses",
                "confidence": 0.85,
                "reason": "Explicit revert in decision title",
            }
    return None


class DecisionLinker:
    """Classifies relations between candidate decision pairs and updates FalkorDB."""

    def __init__(self, concurrency: int = 8):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.model = settings.extract_model
        self.api_key = settings.google_api_key

    async def _classify_llm(self, newer: dict[str, Any], older: dict[str, Any]) -> dict[str, Any]:
        """Classify decision relation using Gemini with caching."""
        cache_key = hashlib.sha1(f"{self.model}:{newer['id']}:{older['id']}".encode()).hexdigest()
        cache_file = CACHE_DIR / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        if not self.api_key:
            return {"relation": "none", "confidence": 0.0, "reason": "No API key"}

        prompt = f"""Evaluate relation from NEWER decision to OLDER decision:

[NEWER DECISION]
ID: {newer.get("id")}
Title: {newer.get("title")}
Summary: {newer.get("summary")}
Date: {newer.get("decided_at")}

[OLDER DECISION]
ID: {older.get("id")}
Title: {older.get("title")}
Summary: {older.get("summary")}
Date: {older.get("decided_at")}
"""
        async with self.semaphore:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.api_key)
                config = types.GenerateContentConfig(
                    system_instruction=LINK_SYSTEM_PROMPT,
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=LINK_JSON_SCHEMA,
                )
                response = await client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                result = json.loads(response.text or "{}")
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)
                return result
            except Exception as exc:
                logger.debug(
                    "Classification failed for %s vs %s: %s", newer["id"], older["id"], exc
                )
                return {"relation": "none", "confidence": 0.0, "reason": str(exc)}

    async def link_decisions(
        self,
        graph: Any | None = None,
        max_pairs: int = 600,
        min_confidence: float = 0.6,
    ) -> dict[str, Any]:
        """Discover candidate pairs, classify relations, and write edges into FalkorDB."""
        if graph is None:
            graph = get_graph()

        candidates = find_candidate_pairs(graph, max_pairs=max_pairs)
        logger.info("Found %s candidate decision pairs for linking.", len(candidates))

        counts: dict[str, int] = {
            "supersedes": 0,
            "reverses": 0,
            "depends_on": 0,
            "conflicts_with": 0,
        }
        chains: list[dict[str, Any]] = []

        async def process_pair(pair: dict[str, Any]) -> None:
            older = pair["older"]
            newer = pair["newer"]

            # 1. Check explicit revert
            res = detect_explicit_revert(newer, older)
            if not res:
                # 2. LLM classification
                res = await self._classify_llm(newer, older)

            rel = res.get("relation", "none").lower()
            conf = float(res.get("confidence", 0.0))
            reason = str(res.get("reason", ""))

            if rel in counts and conf >= min_confidence:
                counts[rel] += 1
                edge_type = rel.upper()

                # Write Cypher edge
                cypher = f"""
                MATCH (newer:Decision {{id: $newer_id}}), (older:Decision {{id: $older_id}})
                MERGE (newer)-[r:{edge_type}]->(older)
                SET r.confidence = $conf, r.reason = $reason
                """
                graph.query(
                    cypher,
                    params={
                        "newer_id": newer["id"],
                        "older_id": older["id"],
                        "conf": conf,
                        "reason": reason,
                    },
                )

                # Update status and valid_to on older decision
                if rel == "supersedes":
                    graph.query(
                        """
                        MATCH (older:Decision {id: $older_id})
                        SET older.status = 'superseded', older.valid_to = $valid_to
                        """,
                        params={"older_id": older["id"], "valid_to": newer.get("decided_at")},
                    )
                elif rel == "reverses":
                    graph.query(
                        """
                        MATCH (older:Decision {id: $older_id})
                        SET older.status = 'reversed', older.valid_to = $valid_to
                        """,
                        params={"older_id": older["id"], "valid_to": newer.get("decided_at")},
                    )

                chains.append(
                    {
                        "newer": newer.get("title"),
                        "newer_date": newer.get("decided_at"),
                        "older": older.get("title"),
                        "older_date": older.get("decided_at"),
                        "relation": rel,
                        "confidence": conf,
                    }
                )

        tasks = [process_pair(pair) for pair in candidates]
        await asyncio.gather(*tasks)

        logger.info("Linking complete! Relation counts: %s", counts)
        return {"counts": counts, "chains": chains}
