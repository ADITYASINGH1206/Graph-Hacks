"""Evidence verification: strictly confirms that LLM evidence quotes are true substrings of source blocks."""

import re
from typing import Any

CURLY_QUOTES_TRANSLATION = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "`": "'",
    }
)


def normalize_text(text: str) -> str:
    """Normalize whitespace and curly quotes for robust substring comparison."""
    if not text:
        return ""
    # Replace curly quotes and unicode dashes
    t = text.translate(CURLY_QUOTES_TRANSLATION)
    # Collapse multiple whitespace characters into a single space
    return re.sub(r"\s+", " ", t).strip()


def verify_evidence_quote(quote: str, block_text: str) -> bool:
    """Return True if whitespace- and quote-normalized quote is a contiguous substring of block_text."""
    q_norm = normalize_text(quote)
    b_norm = normalize_text(block_text)
    if not q_norm or not b_norm:
        return False
    return q_norm in b_norm


def verify_extracted_decision(
    decision: dict[str, Any],
    blocks_by_id: dict[str, str],
) -> tuple[dict[str, Any] | None, int, int]:
    """Verify all evidence quotes for an extracted decision.

    Drops unverified evidence quotes. If a decision has 0 verified quotes remaining,
    the entire decision is dropped.
    Returns: (verified_decision or None, kept_count, dropped_count)
    """
    raw_evidence = decision.get("evidence", [])
    verified_evidence: list[dict[str, Any]] = []
    kept = 0
    dropped = 0

    for ev in raw_evidence:
        block_id = ev.get("block_id", "")
        quote = ev.get("quote", "")
        block_text = blocks_by_id.get(block_id, "")

        if verify_evidence_quote(quote, block_text):
            kept += 1
            # Truncate stored quote to 400 chars
            truncated_quote = quote[:400]
            verified_evidence.append(
                {
                    "block_id": block_id,
                    "quote": truncated_quote,
                }
            )
        else:
            dropped += 1

    if not verified_evidence:
        # Decision has no verified evidence left; drop it per trust guarantee
        return None, kept, dropped

    decision_copy = dict(decision)
    decision_copy["evidence"] = verified_evidence
    return decision_copy, kept, dropped
