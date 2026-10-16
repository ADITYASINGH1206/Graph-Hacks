"""Normalization of raw GitHub issues, PRs, comments, and reviews into Thread and Block models."""

import re
from typing import Any

from pydantic import BaseModel, Field

CLOSES_REGEX = re.compile(
    r"(?i)(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:#|https?://github\.com/[^/\s]+/[^/\s]+/(?:issues|pull)/)(\d+)"
)
REF_NUMBER_REGEX = re.compile(r"#(\d+)")
REF_URL_REGEX = re.compile(r"https?://github\.com/[^/\s]+/[^/\s]+/(?:issues|pull)/(\d+)")


class Block(BaseModel):
    """A contiguous unit of communication in a thread (body, comment, review)."""

    id: str = Field(description="Canonical block identifier e.g. pr:77#body or pr:77#review:9")
    kind: str = Field(
        description="Block type: issue_body | pr_body | comment | review | review_comment | release_note"
    )
    author: str
    ts: str
    url: str
    text: str


class Thread(BaseModel):
    """Normalized GitHub conversation thread (Issue or PullRequest)."""

    source_id: str = Field(description="Unique thread key e.g. issue:123 or pr:77")
    kind: str = Field(description="'issue' or 'pr'")
    number: int
    title: str
    state: str
    url: str
    labels: list[str] = Field(default_factory=list)
    author: str
    is_author_bot: bool = False
    created_at: str
    closed_at: str | None = None
    merged_at: str | None = None
    updated_at: str
    body: str = ""
    blocks: list[Block] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    closes: list[int] = Field(default_factory=list)
    references: list[int] = Field(default_factory=list)


def is_bot_user(user_dict: dict[str, Any] | None) -> bool:
    """Determine whether a GitHub user is an automated bot."""
    if not user_dict:
        return False
    user_type = user_dict.get("type", "")
    login = user_dict.get("login", "")
    if user_type == "Bot" or login.endswith("[bot]"):
        return True
    lower = login.lower()
    return lower.endswith("-bot") or lower.endswith("_bot")


def extract_closes_and_references(text: str, current_number: int) -> tuple[list[int], list[int]]:
    """Parse closes and references numbers from markdown text."""
    closes_set: set[int] = set()
    for match in CLOSES_REGEX.finditer(text):
        num = int(match.group(1))
        if num != current_number:
            closes_set.add(num)

    references_set: set[int] = set()
    for match in REF_NUMBER_REGEX.finditer(text):
        num = int(match.group(1))
        if num != current_number and num not in closes_set:
            references_set.add(num)
    for match in REF_URL_REGEX.finditer(text):
        num = int(match.group(1))
        if num != current_number and num not in closes_set:
            references_set.add(num)

    return sorted(closes_set), sorted(references_set)


def normalize_thread(raw_data: dict[str, Any]) -> Thread:
    """Normalize raw thread payload containing item, comments, reviews, files."""
    item = raw_data.get("item", raw_data)
    number = int(item["number"])
    is_pr = "pull_request" in item or raw_data.get("kind") == "pulls"
    kind = "pr" if is_pr else "issue"
    source_id = f"{kind}:{number}"

    user = item.get("user") or {}
    author = user.get("login", "ghost")
    is_author_bot = is_bot_user(user)

    title = item.get("title", "")
    state = item.get("state", "open")
    html_url = item.get("html_url", "")
    created_at = item.get("created_at", "")
    closed_at = item.get("closed_at")
    merged_at = item.get("pull_request", {}).get("merged_at") or item.get("merged_at")
    updated_at = item.get("updated_at", created_at)
    body = item.get("body") or ""

    labels = [lbl["name"] if isinstance(lbl, dict) else str(lbl) for lbl in item.get("labels", [])]

    blocks: list[Block] = []

    # 1. Main body block
    if body:
        blocks.append(
            Block(
                id=f"{source_id}#body",
                kind="pr_body" if is_pr else "issue_body",
                author=author,
                ts=created_at,
                url=html_url,
                text=body,
            )
        )

    # 2. Issue comments
    comments = raw_data.get("comments", [])
    for c in comments:
        c_body = c.get("body") or ""
        if not c_body.strip():
            continue
        c_user = c.get("user") or {}
        c_author = c_user.get("login", "ghost")
        c_id = c.get("id", "")
        c_url = c.get("html_url", f"{html_url}#issuecomment-{c_id}")
        blocks.append(
            Block(
                id=f"{source_id}#c{c_id}",
                kind="comment",
                author=c_author,
                ts=c.get("created_at", ""),
                url=c_url,
                text=c_body,
            )
        )

    # 3. PR reviews & review comments
    reviews = raw_data.get("reviews", [])
    for r in reviews:
        r_body = r.get("body") or ""
        if not r_body.strip():
            continue
        r_user = r.get("user") or {}
        r_author = r_user.get("login", "ghost")
        r_id = r.get("id", "")
        r_url = r.get("html_url", f"{html_url}#pullrequestreview-{r_id}")
        blocks.append(
            Block(
                id=f"{source_id}#review:{r_id}",
                kind="review",
                author=r_author,
                ts=r.get("submitted_at") or r.get("created_at", ""),
                url=r_url,
                text=r_body,
            )
        )

    review_comments = raw_data.get("review_comments", [])
    for rc in review_comments:
        rc_body = rc.get("body") or ""
        if not rc_body.strip():
            continue
        rc_user = rc.get("user") or {}
        rc_author = rc_user.get("login", "ghost")
        rc_id = rc.get("id", "")
        rc_url = rc.get("html_url", f"{html_url}#discussion_r{rc_id}")
        blocks.append(
            Block(
                id=f"{source_id}#rc{rc_id}",
                kind="review_comment",
                author=rc_author,
                ts=rc.get("created_at", ""),
                url=rc_url,
                text=rc_body,
            )
        )

    # Sort blocks chronologically
    blocks.sort(key=lambda b: b.ts)

    # Extract files changed
    files: list[str] = []
    raw_files = raw_data.get("files", [])
    for f in raw_files:
        filename = f.get("filename") if isinstance(f, dict) else str(f)
        if filename:
            files.append(filename)

    # Extract closes and references across body and comments
    full_text = " ".join([body] + [b.text for b in blocks])
    closes_list, refs_list = extract_closes_and_references(full_text, number)

    return Thread(
        source_id=source_id,
        kind=kind,
        number=number,
        title=title,
        state=state,
        url=html_url,
        labels=labels,
        author=author,
        is_author_bot=is_author_bot,
        created_at=created_at,
        closed_at=closed_at,
        merged_at=merged_at,
        updated_at=updated_at,
        body=body,
        blocks=blocks,
        files=files,
        closes=closes_list,
        references=refs_list,
    )
