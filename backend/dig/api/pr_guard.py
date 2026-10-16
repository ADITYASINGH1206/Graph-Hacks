"""Fetch a GitHub pull request for PR Guard.

Only ``https://github.com/<owner>/<repo>/pull/<n>`` URLs are accepted and every request goes
to api.github.com, so a user-supplied link can never make the server call an arbitrary host.
"""

import re
from typing import Any

import httpx
from dig.config import settings
from dig.ingest.github import GITHUB_API_BASE
from pydantic import BaseModel

PR_URL_RE = re.compile(
    r"^https://github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/"
    r"(?P<repo>[A-Za-z0-9._-]{1,100})/"
    r"pull/(?P<number>[0-9]{1,7})"
    r"(?:/(?:files|commits|checks))?/?(?:[?#].*)?$"
)
MAX_FILES = 100
MAX_BODY_CHARS = 3000


class PRFetchError(Exception):
    """Raised when the PR cannot be retrieved. ``status`` is the HTTP status to return."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class PullRequestData(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    body: str
    state: str
    author: str
    url: str
    additions: int
    deletions: int
    changed_files: int
    files: list[str]
    truncated_files: bool


def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Validate a PR URL and return (owner, repo, number). Raises ValueError if invalid."""
    match = PR_URL_RE.match(url.strip())
    if not match:
        raise ValueError("Expected a link like https://github.com/<owner>/<repo>/pull/<number>")
    return match["owner"], match["repo"], int(match["number"])


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "decision-archaeologist"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def _get(client: httpx.Client, path: str, params: dict[str, Any] | None = None) -> Any:
    try:
        res = client.get(f"{GITHUB_API_BASE}{path}", params=params, headers=_headers())
    except httpx.HTTPError as exc:
        raise PRFetchError(502, f"Could not reach GitHub: {type(exc).__name__}") from exc
    if res.status_code == 404:
        raise PRFetchError(404, "Pull request not found (or the repository is private).")
    if res.status_code in (403, 429):
        raise PRFetchError(
            429, "GitHub rate limit reached. Set GITHUB_TOKEN to raise the limit, then retry."
        )
    if not res.is_success:
        # Includes 3xx: redirects are deliberately not followed.
        raise PRFetchError(502, f"GitHub returned HTTP {res.status_code}.")
    try:
        return res.json()
    except ValueError as exc:
        raise PRFetchError(502, "GitHub returned an unreadable response.") from exc


def fetch_pr(owner: str, repo: str, number: int) -> PullRequestData:
    """Retrieve PR metadata and changed file paths (first 100 files)."""
    # follow_redirects stays False: GitHub's API should answer directly.
    with httpx.Client(timeout=15.0, follow_redirects=False) as client:
        pr = _get(client, f"/repos/{owner}/{repo}/pulls/{number}")
        files = _get(client, f"/repos/{owner}/{repo}/pulls/{number}/files", {"per_page": MAX_FILES})
    changed = int(pr.get("changed_files") or len(files))
    return PullRequestData(
        owner=owner,
        repo=repo,
        number=number,
        title=str(pr.get("title") or ""),
        body=str(pr.get("body") or "")[:MAX_BODY_CHARS],
        state="merged" if pr.get("merged") else str(pr.get("state") or "unknown"),
        author=str((pr.get("user") or {}).get("login") or "unknown"),
        url=str(pr.get("html_url") or f"https://github.com/{owner}/{repo}/pull/{number}"),
        additions=int(pr.get("additions") or 0),
        deletions=int(pr.get("deletions") or 0),
        changed_files=changed,
        files=[str(f.get("filename")) for f in files if f.get("filename")][:MAX_FILES],
        truncated_files=changed > MAX_FILES,
    )
