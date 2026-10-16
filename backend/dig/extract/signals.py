"""Signal scoring filter to identify GitHub threads likely containing architectural decisions."""

import re
from typing import Any

LABEL_KEYWORDS = ["deprecat", "breaking", "rfc", "design", "proposal", "wontfix", "removal"]

TITLE_BODY_REGEX = re.compile(
    r"(?i)\b(deprecat\w*|remov\w*|drop support|revert\w*|breaking change|no longer|instead of|we (?:decided|agreed)|going with|won't fix|rename\w*)\b"
)


def score_thread(thread: dict[str, Any]) -> int:
    """Calculate decision signal score for a normalized thread dictionary."""
    score = 0

    # 1. Label match (+3)
    labels = thread.get("labels", [])
    for lbl in labels:
        lbl_lower = lbl.lower() if isinstance(lbl, str) else str(lbl).lower()
        if any(kw in lbl_lower for kw in LABEL_KEYWORDS):
            score += 3
            break

    # 2. Title or body keyword match (+2)
    title = thread.get("title", "")
    body = thread.get("body", "")
    if TITLE_BODY_REGEX.search(title) or TITLE_BODY_REGEX.search(body):
        score += 2

    # 3. Merged PR touching 5+ files or with 3+ reviews (+2)
    if thread.get("kind") == "pr" and thread.get("merged_at"):
        num_files = len(thread.get("files", []))
        # Count review blocks
        review_count = sum(
            1 for b in thread.get("blocks", []) if b.get("kind") in ("review", "review_comment")
        )
        if num_files >= 5 or review_count >= 3:
            score += 2

    # 4. Thread with 6+ comments (+1)
    comment_count = sum(1 for b in thread.get("blocks", []) if b.get("kind") == "comment")
    if comment_count >= 6:
        score += 1

    return score


def filter_threads(
    threads: list[dict[str, Any]],
    threshold: int = 2,
) -> list[tuple[dict[str, Any], int]]:
    """Filter threads meeting the signal score threshold, sorted by score descending."""
    scored: list[tuple[dict[str, Any], int]] = []
    for t in threads:
        s = score_thread(t)
        if s >= threshold:
            scored.append((t, s))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored
