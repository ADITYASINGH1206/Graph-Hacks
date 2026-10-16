"""FastAPI application exposing Decision Archaeologist API and SSE stream."""

import logging

from dig.agent.agent import DecisionAgent
from dig.api.models import (
    AskRequest,
    DecisionDetailResponse,
    DecisionsListResponse,
    DecisionTimelineItem,
    GuardRequest,
    GuardResponse,
    HealthResponse,
    PersonDecisionItem,
    PersonDetailResponse,
    PersonModuleItem,
    SyncResponse,
)
from dig.api.sse import format_sse_stream
from dig.config import settings
from dig.graph.client import get_graph
from dig.graph.models import GraphElements
from dig.graph.queries import (
    edge_to_graph_edge,
    get_decision,
    get_lineage,
    impact_of,
    node_to_graph_node,
    search_decisions,
)
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Decision Archaeologist API",
    description="Graph-native context layer for repository decision history",
    version="0.1.0",
)

# Enable CORS for Vite dev server (port 5173) and local clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return system health and node counts across primary graph labels."""
    graph = get_graph()
    counts: dict[str, int] = {
        "Decision": 0,
        "Evidence": 0,
        "Person": 0,
        "Issue": 0,
        "PullRequest": 0,
    }

    try:
        for label in counts:
            res = graph.query(f"MATCH (n:{label}) RETURN count(n)")
            if res.result_set:
                counts[label] = int(res.result_set[0][0])
    except Exception as exc:
        logger.warning("Could not fetch entity counts from graph: %s", exc)

    last_synced = None
    try:
        res = graph.query("MATCH (m:Meta) RETURN m.last_synced LIMIT 1")
        if res.result_set and res.result_set[0][0]:
            last_synced = str(res.result_set[0][0])
    except Exception:
        pass

    return HealthResponse(
        ok=True,
        graph=graph.name,
        counts=counts,
        last_synced=last_synced,
    )


@app.post("/ask")
async def ask_endpoint(payload: AskRequest):
    """Execute decision inquiry agent and stream real-time events via SSE."""
    agent = DecisionAgent(repo=settings.target_repo)
    stream = agent.ask_stream(
        question=payload.question,
        session_id=payload.session_id,
        user_id=payload.user_id,
    )
    return StreamingResponse(
        format_sse_stream(stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/guard", response_model=GuardResponse)
def guard_endpoint(payload: GuardRequest) -> GuardResponse:
    """Check a proposed change against past decisions (Decision Guard)."""
    from dig.agent.guard import run_decision_guard

    res = run_decision_guard(description=payload.description, paths=payload.paths)
    return GuardResponse(
        conflicts=res.get("conflicts", []),
        alignments=res.get("alignments", []),
        reversed_before=res.get("reversed_before", []),
        graph=GraphElements(**res.get("graph", {})),
    )


@app.get("/decisions", response_model=DecisionsListResponse)
def list_decisions(
    q: str | None = Query(None, description="Search query string"),
    module: str | None = Query(None, description="Filter by module"),
    status: str | None = Query(None, description="Filter by status (active/superseded/reversed)"),
    type: str | None = Query(None, description="Filter by type (architectural/deprecation/api_design/refactor)"),
    limit: int = Query(50, ge=1, le=200),
) -> DecisionsListResponse:
    """List decisions for the timeline with optional filtering."""
    graph = get_graph()
    res = search_decisions(
        graph,
        query=q or "",
        module=module,
        status=status,
        decision_type=type,
        limit=limit,
    )

    items = []
    for d in res.data:
        items.append(
            DecisionTimelineItem(
                id=d.id,
                title=d.title,
                type=d.type,
                status=d.status,
                decided_at=d.decided_at,
                modules=d.modules,
                confidence=getattr(d, "confidence", getattr(d, "score", 1.0)),
            )
        )
    return DecisionsListResponse(items=items)


@app.get("/decisions/{decision_id}", response_model=DecisionDetailResponse)
def get_decision_detail(decision_id: str) -> DecisionDetailResponse:
    """Retrieve full decision details, citations, people, lineage hops, and impact."""
    graph = get_graph()
    dec_res = get_decision(graph, decision_id)
    if not dec_res.data:
        raise HTTPException(status_code=404, detail=f"Decision '{decision_id}' not found.")

    dec = dec_res.data
    lineage_res = get_lineage(graph, decision_id)
    impact_res = impact_of(graph, decision_id)

    people_list = [p.model_dump() for p in dec.people]
    evidence_list = []
    for n, ev in enumerate(dec.evidence, 1):
        evidence_list.append(
            {
                "n": n,
                "evidence_id": ev.id,
                "quote": ev.quote,
                "url": ev.url,
                "author": ev.author,
                "ts": ev.ts,
                "decision_id": decision_id,
            }
        )

    return DecisionDetailResponse(
        decision=dec.model_dump(),
        evidence=evidence_list,
        people=people_list,
        lineage=lineage_res.graph_elements,
        impact=impact_res.data.model_dump() if impact_res.data else {},
        stale=False,
    )


@app.get("/subgraph", response_model=GraphElements)
def get_subgraph(
    center: str = Query(..., description="Center node UID (e.g. Decision:dec_123, Person:davidism)"),
    depth: int = Query(1, ge=1, le=2),
    limit: int = Query(80, ge=1, le=200),
) -> GraphElements:
    """Expand neighbor subgraph surrounding a central node."""
    graph = get_graph()
    elements = GraphElements()

    # Determine node label and search criteria
    # Node uid may be "Label:id" or pure id
    parts = center.split(":", 1)
    label_filter = f":{parts[0]}" if len(parts) == 2 else ""
    id_val = parts[1] if len(parts) == 2 else parts[0]

    cypher = f"""
    MATCH (c{label_filter})
    WHERE c.id = $id_val OR c.login = $id_val OR c.uid = $center
    MATCH (c)-[r]-(n)
    RETURN c, r, n
    LIMIT $limit
    """
    try:
        res = graph.query(cypher, params={"id_val": id_val, "center": center, "limit": limit})
        seen_nodes = set()
        seen_edges = set()
        if res.result_set:
            for row in res.result_set:
                c_node = node_to_graph_node(row[0])
                r_rel = row[1]
                n_node = node_to_graph_node(row[2])
                if c_node.id not in seen_nodes:
                    elements.nodes.append(c_node)
                    seen_nodes.add(c_node.id)
                if n_node.id not in seen_nodes:
                    elements.nodes.append(n_node)
                    seen_nodes.add(n_node.id)
                e = edge_to_graph_edge(r_rel, c_node.id, n_node.id)
                if e.id not in seen_edges:
                    elements.edges.append(e)
                    seen_edges.add(e.id)
    except Exception as exc:
        logger.warning("Error fetching subgraph for %s: %s", center, exc)

    return elements


@app.post("/sync", response_model=SyncResponse)
def trigger_sync(background_tasks: BackgroundTasks) -> SyncResponse:
    """Trigger incremental repository sync in the background."""
    import asyncio

    from dig.sync import run_incremental_sync

    background_tasks.add_task(asyncio.run, run_incremental_sync())
    return SyncResponse(started=True)


@app.get("/people/{login}", response_model=PersonDetailResponse)
def get_person_detail(login: str) -> PersonDetailResponse:
    """Retrieve expertise scores across modules and decisions made by an engineer."""
    graph = get_graph()

    # Query module expertise
    cypher_mods = """
    MATCH (p:Person {login: $login})-[k:KNOWS]->(m:Module)
    RETURN m.name, k.score
    ORDER BY k.score DESC LIMIT 20
    """
    res_mods = graph.query(cypher_mods, params={"login": login})
    modules = []
    if res_mods.result_set:
        for row in res_mods.result_set:
            modules.append(PersonModuleItem(name=row[0], score=float(row[1] or 0.0)))

    # Query decisions made
    cypher_decs = """
    MATCH (p:Person {login: $login})-[m:MADE]->(d:Decision)
    RETURN d.id, d.title, m.role
    ORDER BY d.decided_at DESC LIMIT 20
    """
    res_decs = graph.query(cypher_decs, params={"login": login})
    decisions = []
    if res_decs.result_set:
        for row in res_decs.result_set:
            decisions.append(PersonDecisionItem(id=row[0], title=row[1], role=row[2] or "maintainer"))

    return PersonDetailResponse(
        login=login,
        modules=modules,
        decisions=decisions,
    )
