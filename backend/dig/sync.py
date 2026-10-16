"""Incremental synchronization runner for newly created or modified GitHub threads."""

import datetime
import logging
from typing import Any

from dig.config import settings
from dig.extract.expertise import compute_and_write_expertise
from dig.extract.extractor import DecisionExtractor
from dig.extract.linker import DecisionLinker
from dig.extract.signals import filter_threads
from dig.graph.client import get_graph
from dig.graph.loader import load_decisions, load_structure
from dig.ingest.github import GitHubClient

logger = logging.getLogger(__name__)


async def run_incremental_sync(repo: str | None = None) -> dict[str, Any]:
    """Fetch updated threads since last sync, extract decisions, link, and update expertise."""
    target_repo = repo or settings.target_repo
    graph = get_graph()

    # Query last sync timestamp
    last_synced = None
    try:
        res = graph.query("MATCH (m:Meta) RETURN m.last_synced LIMIT 1")
        if res.result_set and res.result_set[0][0]:
            last_synced = str(res.result_set[0][0])
    except Exception:
        pass

    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    logger.info("Starting incremental sync for %s (since: %s)...", target_repo, last_synced)

    client = GitHubClient(repo=target_repo)
    threads_updated = 0
    decisions_added = 0

    try:
        # Fetch updated threads from GitHub
        threads = await client.ingest_repo(
            repo=target_repo,
            max_threads=50,
            since=last_synced,
        )
        threads_updated = len(threads)

        if threads:
            # Update structural graph
            load_structure(repo=target_repo)

            # Filter qualifying threads
            qualifying = filter_threads(threads, threshold=2)
            if qualifying:
                extractor = DecisionExtractor()
                decisions, stats = await extractor.extract_and_verify_all(
                    [t for t, _ in qualifying]
                )
                decisions_added = len(decisions)
                if decisions:
                    load_decisions(decisions=decisions, repo=target_repo)
                    linker = DecisionLinker()
                    await linker.link_decisions(max_pairs=100, min_confidence=0.6)

            # Recompute expertise
            compute_and_write_expertise()

        # Update Meta last_synced
        graph.query(
            "MERGE (m:Meta) SET m.last_synced = $ts",
            params={"ts": now_iso},
        )
    finally:
        await client.close()

    return {
        "ok": True,
        "repo": target_repo,
        "threads_updated": threads_updated,
        "decisions_added": decisions_added,
        "last_synced": now_iso,
    }
