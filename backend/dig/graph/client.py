"""FalkorDB client connection and graph access."""

import logging
from typing import Any

import falkordb

from dig.config import settings

logger = logging.getLogger(__name__)


def get_client() -> falkordb.FalkorDB:
    """Connect to FalkorDB instance using environment configuration."""
    return falkordb.FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port)


def get_graph(name: str | None = None) -> Any:
    """Get a FalkorDB Graph object.

    Defaults to the canonical graph for settings.target_repo.
    """
    graph_name = name or settings.graph_name
    client = get_client()
    return client.select_graph(graph_name)


def check_health(name: str | None = None) -> dict[str, Any]:
    """Check connectivity to FalkorDB and retrieve basic node statistics."""
    graph_name = name or settings.graph_name
    try:
        graph = get_graph(graph_name)
        # Test basic query
        res = graph.query("RETURN 1 AS ping")
        if not res.result_set or res.result_set[0][0] != 1:
            return {"ok": False, "graph": graph_name, "error": "Unexpected ping response"}

        # Fetch node counts for core labels
        labels = ["Decision", "Evidence", "Person", "Issue", "PullRequest"]
        counts: dict[str, int] = {}
        for label in labels:
            try:
                c_res = graph.query(f"MATCH (n:{label}) RETURN count(n) AS cnt")
                counts[label] = int(c_res.result_set[0][0]) if c_res.result_set else 0
            except Exception as e:
                logger.debug("Failed to count label %s: %s", label, e)
                counts[label] = 0

        # Check for Meta node last_synced
        last_synced = None
        try:
            m_res = graph.query("MATCH (m:Meta) RETURN m.last_synced AS last_synced LIMIT 1")
            if m_res.result_set and m_res.result_set[0][0]:
                last_synced = str(m_res.result_set[0][0])
        except Exception as e:
            logger.debug("Meta node not found: %s", e)

        return {
            "ok": True,
            "graph": graph_name,
            "counts": counts,
            "last_synced": last_synced,
        }
    except Exception as exc:
        logger.warning("FalkorDB health check failed for %s: %s", graph_name, exc)
        return {
            "ok": False,
            "graph": graph_name,
            "error": str(exc),
            "counts": {},
            "last_synced": None,
        }
