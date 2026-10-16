"""Graph-derived insights: historical snapshots (Time Machine) and knowledge-risk scoring.

Database access is kept in the ``fetch_*`` functions; everything else is pure so it can be
unit-tested without a running graph.
"""

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, Field

from dig.graph.models import GraphEdge, GraphElements, GraphNode
from dig.graph.queries import node_to_graph_node

RiskLevel = Literal["critical", "high", "medium", "low"]

# --------------------------------------------------------------------------- helpers


def parse_ts(value: Any) -> dt.datetime | None:
    """Parse an ISO date or datetime (``2022-03-20`` or ``2022-03-20T16:00:00Z``) as UTC."""
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def iso(value: dt.datetime | None) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


# --------------------------------------------------------------------------- time machine


class DecisionRecord(BaseModel):
    """A decision with the dates needed to place it on a timeline."""

    id: str
    node: GraphNode
    modules: list[GraphNode] = Field(default_factory=list)
    start: dt.datetime | None = None
    end: dt.datetime | None = None


class Relation(BaseModel):
    source: str  # newer decision id
    target: str  # older decision id
    type: str  # SUPERSEDES | REVERSES
    reason: str = ""


class SnapshotDecision(BaseModel):
    id: str
    title: str
    type: str = ""
    summary: str = ""
    status: str  # status AS OF the chosen date
    decided_at: str | None = None
    ended_at: str | None = None
    modules: list[str] = Field(default_factory=list)


class Snapshot(BaseModel):
    as_of: str
    active: list[SnapshotDecision] = Field(default_factory=list)
    ended: list[SnapshotDecision] = Field(default_factory=list)
    upcoming_count: int = 0
    undated_count: int = 0
    graph: GraphElements = Field(default_factory=GraphElements)


class TimelineEvent(BaseModel):
    date: str
    kind: Literal["decided", "ended"]
    decision_id: str
    title: str


class TimelineRange(BaseModel):
    min_date: str | None = None
    max_date: str | None = None
    events: list[TimelineEvent] = Field(default_factory=list)
    undated_count: int = 0


def fetch_decision_records(graph: Any) -> tuple[list[DecisionRecord], list[Relation]]:
    """Load every decision (with its modules) and the SUPERSEDES/REVERSES links between them."""
    records: list[DecisionRecord] = []
    res = graph.query(
        "MATCH (d:Decision) OPTIONAL MATCH (d)-[:AFFECTS]->(m:Module) RETURN d, collect(DISTINCT m)"
    )
    for row in res.result_set or []:
        node = node_to_graph_node(row[0])
        props = node.props
        start = parse_ts(props.get("valid_from")) or parse_ts(props.get("decided_at"))
        end = parse_ts(props.get("valid_to"))
        modules = [node_to_graph_node(m) for m in (row[1] or []) if m is not None]
        records.append(
            DecisionRecord(
                id=str(props.get("id") or node.id), node=node, modules=modules, start=start, end=end
            )
        )

    relations: list[Relation] = []
    rel_res = graph.query(
        "MATCH (a:Decision)-[r:SUPERSEDES|REVERSES]->(b:Decision) "
        "RETURN a.id, b.id, type(r), r.reason"
    )
    for row in rel_res.result_set or []:
        relations.append(
            Relation(
                source=str(row[0]), target=str(row[1]), type=str(row[2]), reason=str(row[3] or "")
            )
        )
    return records, relations


def compute_range(records: list[DecisionRecord]) -> TimelineRange:
    """Date bounds and ordered start/end events for the Time Machine slider."""
    events: list[TimelineEvent] = []
    undated = 0
    for rec in records:
        title = rec.node.title
        if rec.start is None:
            undated += 1
            continue
        events.append(
            TimelineEvent(
                date=iso(rec.start) or "", kind="decided", decision_id=rec.id, title=title
            )
        )
        if rec.end is not None:
            events.append(
                TimelineEvent(
                    date=iso(rec.end) or "", kind="ended", decision_id=rec.id, title=title
                )
            )
    events.sort(key=lambda e: (e.date, e.kind))
    return TimelineRange(
        min_date=events[0].date if events else None,
        max_date=events[-1].date if events else None,
        events=events,
        undated_count=undated,
    )


def _snapshot_decision(rec: DecisionRecord, status: str) -> SnapshotDecision:
    props = rec.node.props
    return SnapshotDecision(
        id=rec.id,
        title=rec.node.title,
        type=str(props.get("type") or ""),
        summary=str(props.get("summary") or ""),
        status=status,
        decided_at=iso(rec.start),
        ended_at=iso(rec.end),
        modules=[m.title for m in rec.modules],
    )


def compute_snapshot(
    records: list[DecisionRecord], relations: list[Relation], at: dt.datetime
) -> Snapshot:
    """What the project had decided on ``at``, and what had already been replaced by then."""
    active: list[DecisionRecord] = []
    ended: list[DecisionRecord] = []
    upcoming = 0
    undated = 0
    for rec in records:
        if rec.start is None:
            undated += 1
        elif rec.start > at:
            upcoming += 1
        elif rec.end is not None and rec.end <= at:
            ended.append(rec)
        else:
            active.append(rec)

    status_at: dict[str, str] = {}
    for rec in active:
        status_at[rec.id] = "active"
    for rec in ended:
        original = str(rec.node.props.get("status") or "")
        status_at[rec.id] = original if original in ("superseded", "reversed") else "superseded"

    elements = GraphElements()
    seen_nodes: set[str] = set()

    def add_node(node: GraphNode, extra: dict[str, Any] | None = None) -> None:
        if node.id in seen_nodes:
            return
        seen_nodes.add(node.id)
        props = {**node.props, **(extra or {})}
        elements.nodes.append(node.model_copy(update={"props": props}))

    for rec in [*active, *ended]:
        add_node(rec.node, {"status": status_at[rec.id], "as_of": iso(at)})
        for module in rec.modules:
            add_node(module)
            elements.edges.append(
                GraphEdge(
                    id=f"{rec.node.id}->{module.id}:AFFECTS",
                    source=rec.node.id,
                    target=module.id,
                    type="AFFECTS",
                )
            )

    visible = {r.id: r for r in [*active, *ended]}
    for rel in relations:
        if rel.source in visible and rel.target in visible:
            src, dst = visible[rel.source].node.id, visible[rel.target].node.id
            elements.edges.append(
                GraphEdge(
                    id=f"{src}->{dst}:{rel.type}",
                    source=src,
                    target=dst,
                    type=rel.type,
                    props={"reason": rel.reason} if rel.reason else {},
                )
            )

    def ordered(recs: list[DecisionRecord], newest_first: bool) -> list[SnapshotDecision]:
        recs = sorted(recs, key=lambda r: r.start or at, reverse=newest_first)
        return [_snapshot_decision(r, status_at[r.id]) for r in recs]

    return Snapshot(
        as_of=iso(at) or "",
        active=ordered(active, newest_first=True),
        ended=ordered(ended, newest_first=True),
        upcoming_count=upcoming,
        undated_count=undated,
        graph=elements,
    )


# --------------------------------------------------------------------------- knowledge risk


class ExpertRow(BaseModel):
    """One KNOWS edge: how much a person knows a module and when they were last active."""

    module: str
    login: str
    score: float = 0.0
    last_active: str | None = None
    authored: int = 0
    reviewed: int = 0
    commented: int = 0


class ModuleExpert(BaseModel):
    login: str
    score: float
    share: float  # fraction of the module's total expertise
    last_active: str | None = None
    active: bool


class ModuleRisk(BaseModel):
    module: str
    risk: RiskLevel
    risk_score: float  # 0-100, used for the heat colour and ordering
    reasons: list[str] = Field(default_factory=list)
    bus_factor: int  # people needed to cover 60% of the module's expertise (0 = nobody)
    active_experts: int
    experts: list[ModuleExpert] = Field(default_factory=list)
    decisions_total: int = 0
    decisions_active: int = 0


class RiskReport(BaseModel):
    as_of: str
    as_of_source: Literal["graph_latest", "requested", "now"]
    window_days: int
    modules: list[ModuleRisk] = Field(default_factory=list)


_LEVEL_BASE: dict[str, float] = {"critical": 85.0, "high": 62.0, "medium": 38.0, "low": 12.0}
_LEVEL_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_COVERAGE = 0.6


def fetch_expert_rows(graph: Any) -> list[ExpertRow]:
    res = graph.query(
        "MATCH (p:Person)-[k:KNOWS]->(m:Module) "
        "WHERE p.is_bot IS NULL OR p.is_bot = false "
        "RETURN m.name, p.login, k.score, k.last_active, k.authored, k.reviewed, k.commented"
    )
    rows: list[ExpertRow] = []
    for r in res.result_set or []:
        rows.append(
            ExpertRow(
                module=str(r[0]),
                login=str(r[1]),
                score=float(r[2] or 0.0),
                last_active=str(r[3]) if r[3] else None,
                authored=int(r[4] or 0),
                reviewed=int(r[5] or 0),
                commented=int(r[6] or 0),
            )
        )
    return rows


def fetch_decision_statuses(graph: Any) -> dict[str, list[str]]:
    """Map module name -> list of statuses of the decisions that affect it."""
    res = graph.query("MATCH (d:Decision)-[:AFFECTS]->(m:Module) RETURN m.name, collect(d.status)")
    return {str(r[0]): [str(s or "") for s in (r[1] or [])] for r in (res.result_set or [])}


def _bus_factor(scores: list[float]) -> int:
    total = sum(scores)
    if total <= 0:
        return 0
    covered = 0.0
    for count, score in enumerate(sorted(scores, reverse=True), start=1):
        covered += score
        if covered / total >= _COVERAGE:
            return count
    return len(scores)


def _assess(
    experts: list[ModuleExpert], bus_factor: int, active: int
) -> tuple[RiskLevel, list[str]]:
    if not experts:
        return "critical", ["No known expert in the graph"]
    if active == 0:
        last = max(experts, key=lambda e: e.last_active or "")
        when = f" (last seen: {last.login}, {last.last_active})" if last.last_active else ""
        return "critical", [f"All {len(experts)} known experts are inactive{when}"]
    if active == 1:
        sole = next(e for e in experts if e.active)
        return "high", [f"Only one active expert: {sole.login}"]
    if bus_factor == 1:
        top = experts[0]
        return "medium", [f"Knowledge is concentrated: {top.login} holds {top.share:.0%} of it"]
    if active == 2:
        return "medium", ["Only two active experts"]
    return "low", [f"{active} active experts share the knowledge"]


def compute_module_risk(
    rows: list[ExpertRow],
    decision_statuses: dict[str, list[str]],
    as_of: dt.datetime,
    window_days: int = 365,
) -> list[ModuleRisk]:
    """Score each module by how fragile its knowledge is (few, concentrated or inactive experts)."""
    cutoff = as_of - dt.timedelta(days=window_days)
    by_module: dict[str, list[ExpertRow]] = {}
    for row in rows:
        by_module.setdefault(row.module, []).append(row)
    for name in decision_statuses:
        by_module.setdefault(name, [])

    max_decisions = max((len(s) for s in decision_statuses.values()), default=0)
    report: list[ModuleRisk] = []
    for module, module_rows in by_module.items():
        total = sum(r.score for r in module_rows) or 0.0
        experts = [
            ModuleExpert(
                login=r.login,
                score=round(r.score, 2),
                share=(r.score / total) if total > 0 else 0.0,
                last_active=r.last_active,
                active=bool(
                    (parse_ts(r.last_active) or dt.datetime.min.replace(tzinfo=dt.UTC)) >= cutoff
                ),
            )
            for r in sorted(module_rows, key=lambda r: r.score, reverse=True)
        ]
        active_count = sum(1 for e in experts if e.active)
        bus = _bus_factor([e.score for e in experts])
        level, reasons = _assess(experts, bus, active_count)
        statuses = decision_statuses.get(module, [])
        impact = (len(statuses) / max_decisions) if max_decisions else 0.0
        report.append(
            ModuleRisk(
                module=module,
                risk=level,
                risk_score=round(min(100.0, _LEVEL_BASE[level] + 14.0 * impact), 1),
                reasons=reasons,
                bus_factor=bus,
                active_experts=active_count,
                experts=experts[:5],
                decisions_total=len(statuses),
                decisions_active=sum(1 for s in statuses if s == "active"),
            )
        )
    report.sort(key=lambda m: (_LEVEL_ORDER[m.risk], -m.risk_score, m.module))
    return report


def compute_risk_report(
    rows: list[ExpertRow],
    decision_statuses: dict[str, list[str]],
    requested_as_of: dt.datetime | None = None,
    window_days: int = 365,
    now: dt.datetime | None = None,
) -> RiskReport:
    """Build the report. Default reference date = the newest activity in the graph, so an
    old snapshot is not flagged red just because time has passed since it was ingested."""
    latest = max((d for d in (parse_ts(r.last_active) for r in rows) if d), default=None)
    if requested_as_of is not None:
        as_of, source = requested_as_of, "requested"
    elif latest is not None:
        as_of, source = latest, "graph_latest"
    else:
        as_of, source = now or dt.datetime.now(dt.UTC), "now"
    return RiskReport(
        as_of=iso(as_of) or "",
        as_of_source=source,  # type: ignore[arg-type]
        window_days=window_days,
        modules=compute_module_risk(rows, decision_statuses, as_of, window_days),
    )
