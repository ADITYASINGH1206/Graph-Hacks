"""Time Machine, knowledge-risk map and PR Guard endpoints."""

from typing import Annotated

from dig.agent.guard import run_decision_guard
from dig.api import pr_guard
from dig.api.models import GuardResponse
from dig.config import settings
from dig.graph.client import get_graph
from dig.graph.insights import (
    RiskReport,
    Snapshot,
    TimelineRange,
    compute_range,
    compute_risk_report,
    compute_snapshot,
    fetch_decision_records,
    fetch_decision_statuses,
    fetch_expert_rows,
    parse_ts,
)
from dig.graph.models import GraphElements
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, StringConstraints

router = APIRouter()


@router.get("/timeline/range", response_model=TimelineRange)
def timeline_range() -> TimelineRange:
    """Date bounds and start/end events for the Time Machine slider."""
    records, _ = fetch_decision_records(get_graph())
    return compute_range(records)


@router.get("/timeline/snapshot", response_model=Snapshot)
def timeline_snapshot(
    date: str = Query(..., description="ISO date or datetime, e.g. 2021-06-01"),
) -> Snapshot:
    """What the project had decided on a given date, and what had been replaced by then."""
    at = parse_ts(date)
    if at is None:
        raise HTTPException(status_code=422, detail="date must be an ISO date like 2021-06-01")
    records, relations = fetch_decision_records(get_graph())
    return compute_snapshot(records, relations, at)


@router.get("/risk/modules", response_model=RiskReport)
def risk_modules(
    as_of: str | None = Query(
        None, description="Reference date. Default: the newest activity found in the graph."
    ),
    window_days: int = Query(365, ge=30, le=3650, description="Activity window for 'active'"),
) -> RiskReport:
    """Rank modules by how fragile their knowledge is (few, concentrated or inactive experts)."""
    requested = None
    if as_of:
        requested = parse_ts(as_of)
        if requested is None:
            raise HTTPException(status_code=422, detail="as_of must be an ISO date")
    graph = get_graph()
    return compute_risk_report(
        fetch_expert_rows(graph),
        fetch_decision_statuses(graph),
        requested_as_of=requested,
        window_days=window_days,
    )


PRUrl = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=300)]


class PRGuardRequest(BaseModel):
    url: PRUrl


class PRInfo(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    state: str
    author: str
    url: str
    additions: int
    deletions: int
    changed_files: int
    files_checked: int
    truncated_files: bool


class PRGuardResponse(BaseModel):
    pr: PRInfo
    graph_repo: str
    repo_matches_graph: bool
    guard: GuardResponse
    suggested_reviewers: list[str]


@router.post("/guard/pr", response_model=PRGuardResponse)
def guard_pull_request(payload: PRGuardRequest) -> PRGuardResponse:
    """Check a GitHub pull request against past decisions."""
    try:
        owner, repo, number = pr_guard.parse_pr_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        pr = pr_guard.fetch_pr(owner, repo, number)
    except pr_guard.PRFetchError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc

    result = run_decision_guard(description=f"{pr.title}\n\n{pr.body}".strip(), paths=pr.files)
    guard = GuardResponse(
        conflicts=result.get("conflicts", []),
        alignments=result.get("alignments", []),
        reversed_before=result.get("reversed_before", []),
        graph=GraphElements(**result.get("graph", {})),
        judge=result.get("judge", "heuristic"),
    )

    # People who made the conflicting decisions are the natural reviewers (most severe first).
    reviewers: list[str] = []
    for conflict in sorted(guard.conflicts, key=lambda c: c.confidence, reverse=True):
        for login in conflict.people:
            if login not in reviewers and login != pr.author:
                reviewers.append(login)

    return PRGuardResponse(
        pr=PRInfo(
            owner=pr.owner,
            repo=pr.repo,
            number=pr.number,
            title=pr.title,
            state=pr.state,
            author=pr.author,
            url=pr.url,
            additions=pr.additions,
            deletions=pr.deletions,
            changed_files=pr.changed_files,
            files_checked=len(pr.files),
            truncated_files=pr.truncated_files,
        ),
        graph_repo=settings.target_repo,
        repo_matches_graph=f"{owner}/{repo}".lower() == settings.target_repo.lower(),
        guard=guard,
        suggested_reviewers=reviewers[:5],
    )
