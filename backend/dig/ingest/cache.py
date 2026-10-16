"""Disk cache management for raw GitHub payloads and normalized threads."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BASE_DATA_DIR = Path("data")


def get_repo_raw_dir(repo: str, kind: str) -> Path:
    """Return path to data/raw/{repo_slug}/{kind} ensuring it exists."""
    slug = repo.replace("/", "_").replace("-", "_").lower()
    path = BASE_DATA_DIR / "raw" / slug / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cached_item(repo: str, kind: str, item_id: str | int) -> dict[str, Any] | None:
    """Load cached item from disk if it exists."""
    path = get_repo_raw_dir(repo, kind) / f"{item_id}.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to read cache at %s: %s", path, exc)
        return None


def save_cached_item(repo: str, kind: str, item_id: str | int, data: dict[str, Any]) -> Path:
    """Save raw item payload to disk."""
    path = get_repo_raw_dir(repo, kind) / f"{item_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def is_cache_fresh(repo: str, kind: str, item_id: str | int, updated_at: str | None) -> bool:
    """Check if cached item matches current updated_at timestamp."""
    if not updated_at:
        return False
    cached = get_cached_item(repo, kind, item_id)
    if not cached:
        return False
    cached_updated = cached.get("item", {}).get("updated_at") or cached.get("updated_at")
    return cached_updated == updated_at


def get_normalized_threads_path(repo: str) -> Path:
    """Return path to normalized threads.jsonl for repo."""
    slug = repo.replace("/", "_").replace("-", "_").lower()
    path = BASE_DATA_DIR / "normalized" / slug
    path.mkdir(parents=True, exist_ok=True)
    return path / "threads.jsonl"


def save_normalized_threads(repo: str, threads: list[dict[str, Any]]) -> Path:
    """Save list of normalized Thread dictionaries as json lines."""
    path = get_normalized_threads_path(repo)
    with open(path, "w", encoding="utf-8") as f:
        for t in threads:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    return path


def load_normalized_threads(repo: str) -> list[dict[str, Any]]:
    """Load normalized threads from json lines file if it exists."""
    path = get_normalized_threads_path(repo)
    if not path.exists():
        return []
    threads: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                threads.append(json.loads(line))
    return threads
