"""GitHub REST API client for fetching issues, PRs, comments, reviews, and releases with caching."""

import asyncio
import logging
import time
from typing import Any

import httpx

from dig.config import settings
from dig.ingest.cache import (
    get_cached_item,
    is_cache_fresh,
    save_cached_item,
    save_normalized_threads,
)
from dig.ingest.normalize import normalize_thread

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    """Async GitHub REST client handling auth, pagination, rate limits, and disk caching."""

    def __init__(self, token: str | None = None, repo: str | None = None):
        self.token = token or settings.github_token
        self.repo = repo or settings.target_repo
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Decision-Archaeologist",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

        self.client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True,
        )
        self.network_calls_made = 0

    async def close(self) -> None:
        """Close httpx client."""
        await self.client.aclose()

    async def request_with_retry(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Execute HTTP GET request handling rate limits and backoff."""
        while True:
            self.network_calls_made += 1
            response = await self.client.get(endpoint, params=params)

            # Check rate limits
            remaining = response.headers.get("x-ratelimit-remaining")
            reset_ts = response.headers.get("x-ratelimit-reset")

            if response.status_code in (403, 429) and remaining == "0":
                if reset_ts:
                    wait_seconds = max(1.0, float(reset_ts) - time.time() + 1.0)
                    logger.warning(
                        "GitHub rate limit exceeded. Sleeping for %.1f seconds until reset.",
                        wait_seconds,
                    )
                    await asyncio.sleep(min(wait_seconds, 3600))
                    continue
                else:
                    await asyncio.sleep(60.0)
                    continue

            if response.status_code in (404, 422):
                logger.info(
                    "HTTP %s for %s - ending pagination or resource not found.",
                    response.status_code,
                    endpoint,
                )
                return None

            response.raise_for_status()
            return response.json()

    async def fetch_paginated(
        self, endpoint: str, params: dict[str, Any] | None = None, max_items: int | None = None
    ) -> list[Any]:
        """Fetch all items from a paginated GitHub endpoint."""
        query_params = dict(params or {})
        query_params.setdefault("per_page", 100)
        page = 1
        results: list[Any] = []

        while True:
            query_params["page"] = page
            data = await self.request_with_retry(endpoint, params=query_params)
            if not data or not isinstance(data, list):
                break
            results.extend(data)
            if len(data) < query_params["per_page"] or (max_items and len(results) >= max_items):
                break
            page += 1

        if max_items:
            results = results[:max_items]
        return results

    async def ingest_thread_details(self, repo: str, item: dict[str, Any]) -> dict[str, Any]:
        """Fetch child comments, reviews, and changed files for a thread with cache check."""
        number = item["number"]
        is_pr = "pull_request" in item
        kind = "pulls" if is_pr else "issues"
        updated_at = item.get("updated_at")

        # 1. Check disk cache
        if is_cache_fresh(repo, kind, number, updated_at):
            cached = get_cached_item(repo, kind, number)
            if cached:
                return cached

        # 2. Fetch fresh details
        comments: list[Any] = []
        reviews: list[Any] = []
        review_comments: list[Any] = []
        files: list[Any] = []

        # Comments
        comments_endpoint = f"/repos/{repo}/issues/{number}/comments"
        try:
            comments = await self.fetch_paginated(comments_endpoint)
        except Exception as e:
            logger.debug("Failed fetching comments for %s #%s: %s", kind, number, e)

        # For PRs, also fetch reviews, review comments, and files
        if is_pr:
            try:
                reviews = await self.fetch_paginated(f"/repos/{repo}/pulls/{number}/reviews")
            except Exception as e:
                logger.debug("Failed fetching reviews for PR #%s: %s", number, e)

            try:
                review_comments = await self.fetch_paginated(
                    f"/repos/{repo}/pulls/{number}/comments"
                )
            except Exception as e:
                logger.debug("Failed fetching review comments for PR #%s: %s", number, e)

            try:
                files = await self.fetch_paginated(f"/repos/{repo}/pulls/{number}/files")
            except Exception as e:
                logger.debug("Failed fetching files for PR #%s: %s", number, e)

        raw_payload = {
            "item": item,
            "kind": kind,
            "updated_at": updated_at,
            "comments": comments,
            "reviews": reviews,
            "review_comments": review_comments,
            "files": files,
        }

        # Save to disk cache
        save_cached_item(repo, kind, number, raw_payload)
        return raw_payload

    async def ingest_repo(
        self, repo: str | None = None, max_threads: int = 1500
    ) -> list[dict[str, Any]]:
        """Run full ingest for repo up to max_threads, returning normalized threads."""
        target_repo = repo or self.repo
        logger.info("Starting ingest for %s (up to %s threads)...", target_repo, max_threads)

        # Fetch issues list (includes PRs)
        issues_endpoint = f"/repos/{target_repo}/issues"
        params = {"state": "all", "sort": "created", "direction": "desc"}
        items = await self.fetch_paginated(issues_endpoint, params=params, max_items=max_threads)
        logger.info("Found %s threads in %s listing.", len(items), target_repo)

        # Also fetch releases
        try:
            releases = await self.fetch_paginated(f"/repos/{target_repo}/releases", max_items=100)
            for rel in releases:
                tag = rel.get("tag_name") or rel.get("id")
                save_cached_item(target_repo, "releases", tag, rel)
            logger.info("Cached %s releases for %s.", len(releases), target_repo)
        except Exception as e:
            logger.warning("Could not fetch releases: %s", e)

        # Process each thread with bounded concurrency
        semaphore = asyncio.Semaphore(10)
        normalized_threads: list[dict[str, Any]] = []
        processed_count = 0

        async def process_one(item: dict[str, Any]) -> dict[str, Any]:
            nonlocal processed_count
            async with semaphore:
                raw_payload = await self.ingest_thread_details(target_repo, item)
                thread = normalize_thread(raw_payload)
                processed_count += 1
                if processed_count % 50 == 0 or processed_count == len(items):
                    logger.info("Ingested %s / %s threads...", processed_count, len(items))
                return thread.model_dump()

        tasks = [process_one(item) for item in items]
        normalized_threads = await asyncio.gather(*tasks)

        # Save normalized threads.jsonl
        jsonl_path = save_normalized_threads(target_repo, normalized_threads)
        logger.info(
            "Ingestion finished: %s threads saved to %s (Network calls made: %s)",
            len(normalized_threads),
            jsonl_path,
            self.network_calls_made,
        )

        return normalized_threads
