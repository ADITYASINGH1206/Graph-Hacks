"""Decision extractor using LLM (Gemini / Anthropic) with schema enforcement, retry, and disk caching."""

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from dig.config import settings
from dig.extract.prompts import (
    EXTRACTION_JSON_SCHEMA,
    EXTRACTION_SYSTEM_PROMPT,
    format_thread_for_llm,
)
from dig.extract.verify import verify_extracted_decision
from dig.ingest.cache import BASE_DATA_DIR

logger = logging.getLogger(__name__)

CACHE_DIR = BASE_DATA_DIR / "cache" / "extract"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
EXTRACTED_DIR = BASE_DATA_DIR / "extracted"
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_path(model: str, thread_text: str) -> Path:
    """Derive deterministic cache path keyed by sha1(model + prompt_v1 + thread_text)."""
    key = hashlib.sha1(f"{model}:v1:{thread_text}".encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def generate_decision_id(source_id: str, title: str) -> str:
    """Generate canonical Decision.id: dec_ + first 12 hex of sha1(source_id + normalized_title)."""
    norm_title = " ".join(title.lower().split())
    raw = f"{source_id}:{norm_title}".encode()
    h = hashlib.sha1(raw).hexdigest()[:12]
    return f"dec_{h}"


class DecisionExtractor:
    """Asynchronous LLM decision extractor with rate bounding and verification."""

    def __init__(self, concurrency: int = 8):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.model = settings.extract_model
        self.api_key = settings.google_api_key

    async def _call_llm_gemini(self, user_content: str) -> str:
        """Call Gemini model using google-genai SDK."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        config = types.GenerateContentConfig(
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=EXTRACTION_JSON_SCHEMA,
        )
        response = await client.aio.models.generate_content(
            model=self.model,
            contents=user_content,
            config=config,
        )
        return response.text or "{}"

    async def extract_from_thread(self, thread: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract decisions from a single thread with disk caching and retry."""
        thread_text = format_thread_for_llm(thread)
        cache_path = get_cache_path(self.model, thread_text)

        # 1. Check disk cache
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    cached_data = json.load(f)
                    return cached_data.get("decisions", [])
            except Exception as e:
                logger.debug("Cache read error for %s: %s", cache_path, e)

        if not self.api_key:
            logger.warning("No API key configured for decision extraction. Skipping LLM call.")
            return []

        async with self.semaphore:
            # 2. Call LLM with 1 retry on malformed JSON
            raw_text = "{}"
            for attempt in range(2):
                try:
                    raw_text = await self._call_llm_gemini(thread_text)
                    parsed = json.loads(raw_text)
                    decisions = parsed.get("decisions", [])
                    # Cache valid response
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump({"decisions": decisions}, f, indent=2)
                    return decisions
                except Exception as exc:
                    logger.warning(
                        "Extraction attempt %s failed for %s: %s",
                        attempt + 1,
                        thread.get("source_id"),
                        exc,
                    )
                    if attempt == 0:
                        await asyncio.sleep(1.0)
                    else:
                        return []
        return []

    async def extract_and_verify_all(
        self,
        threads: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """Extract and verify decisions across candidate threads."""
        logger.info(
            "Extracting decisions from %s threads using %s...",
            len(threads),
            self.model,
        )

        all_verified_decisions: list[dict[str, Any]] = []
        total_extracted = 0
        total_kept_evidence = 0
        total_dropped_evidence = 0

        async def process_thread(thread: dict[str, Any]) -> list[dict[str, Any]]:
            nonlocal total_extracted, total_kept_evidence, total_dropped_evidence

            # Map block_id -> text, url, author, ts
            block_map = {b.get("id"): b.get("text", "") for b in thread.get("blocks", [])}
            block_meta = {
                b.get("id"): {
                    "kind": b.get("kind", "comment"),
                    "author": b.get("author", "ghost"),
                    "url": b.get("url", ""),
                    "ts": b.get("ts", ""),
                }
                for b in thread.get("blocks", [])
            }

            raw_decisions = await self.extract_from_thread(thread)
            verified_for_thread: list[dict[str, Any]] = []

            for dec in raw_decisions:
                total_extracted += 1
                verified_dec, kept, dropped = verify_extracted_decision(dec, block_map)
                total_kept_evidence += kept
                total_dropped_evidence += dropped

                if verified_dec:
                    source_id = thread.get("source_id", "")
                    title = verified_dec.get("title", "")
                    dec_id = generate_decision_id(source_id, title)
                    verified_dec["id"] = dec_id
                    verified_dec["source_id"] = source_id
                    verified_dec["source_kind"] = thread.get("kind")
                    verified_dec["source_number"] = thread.get("number")
                    verified_dec["source_url"] = thread.get("url")

                    # Enrich evidence items with metadata
                    enriched_evidence: list[dict[str, Any]] = []
                    for ev in verified_dec.get("evidence", []):
                        b_id = ev.get("block_id")
                        meta = block_meta.get(b_id, {})
                        ev_id = f"ev_{hashlib.sha1(f'{dec_id}:{b_id}'.encode()).hexdigest()[:10]}"
                        enriched_evidence.append(
                            {
                                "id": ev_id,
                                "block_id": b_id,
                                "quote": ev.get("quote"),
                                "kind": meta.get("kind", "comment"),
                                "author": meta.get("author", "ghost"),
                                "url": meta.get("url", thread.get("url")),
                                "ts": meta.get("ts", thread.get("created_at")),
                            }
                        )
                    verified_dec["evidence"] = enriched_evidence
                    verified_for_thread.append(verified_dec)

            return verified_for_thread

        tasks = [process_thread(t) for t in threads]
        results = await asyncio.gather(*tasks)
        for sublist in results:
            all_verified_decisions.extend(sublist)

        # Write to data/extracted/decisions.jsonl
        out_path = EXTRACTED_DIR / "decisions.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for d in all_verified_decisions:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")

        stats = {
            "threads_sent": len(threads),
            "decisions_extracted": total_extracted,
            "decisions_verified": len(all_verified_decisions),
            "evidence_kept": total_kept_evidence,
            "evidence_dropped": total_dropped_evidence,
        }

        logger.info(
            "Extraction complete: %s verified decisions written to %s (Evidence kept: %s, dropped: %s)",
            len(all_verified_decisions),
            out_path,
            total_kept_evidence,
            total_dropped_evidence,
        )
        return all_verified_decisions, stats
