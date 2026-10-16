"""Core parameterised Cypher queries for Decision Archaeologist."""

import logging
from typing import Any

import networkx as nx

from dig.graph.client import get_graph
from dig.graph.models import (
    ActiveDecisionItem,
    DecisionDetail,
    DecisionSearchResult,
    EvidenceItem,
    GraphEdge,
    GraphElements,
    GraphNode,
    ImpactResult,
    LineageHop,
    LineageResult,
    PersonRole,
    QueryResult,
    ShortestPathResult,
    WhoKnowsItem,
)

logger = logging.getLogger(__name__)


def node_to_graph_node(node: Any) -> GraphNode:
    """Convert a FalkorDB Node into a standard GraphNode."""
    labels = getattr(node, "labels", [])
    label = labels[0] if labels else "Node"
    props = dict(getattr(node, "properties", {}))
    uid = props.get("uid")
    if not uid:
        key_val = (
            props.get("id")
            or props.get("number")
            or props.get("login")
            or props.get("name")
            or props.get("tag")
            or props.get("path")
            or getattr(node, "id", "unknown")
        )
        uid = f"{label}:{key_val}"
    title = str(
        props.get("title")
        or props.get("name")
        or props.get("login")
        or props.get("tag")
        or props.get("path")
        or uid
    )
    return GraphNode(id=uid, label=label, title=title, props=props)


def edge_to_graph_edge(edge: Any, source_uid: str, target_uid: str) -> GraphEdge:
    """Convert a FalkorDB Edge into a standard GraphEdge."""
    rel_type = getattr(edge, "relation", "RELATED_TO")
    props = dict(getattr(edge, "properties", {}))
    edge_id = f"{source_uid}->{target_uid}:{rel_type}"
    return GraphEdge(id=edge_id, source=source_uid, target=target_uid, type=rel_type, props=props)


def search_decisions(
    graph: Any,
    query: str = "",
    module: str | None = None,
    decision_type: str | None = None,
    status: str | None = None,
    limit: int = 8,
) -> QueryResult[list[DecisionSearchResult]]:
    """Search decisions, ranked by relevance to the query.

    Candidates are filtered in Cypher (module, status, type; all parameterised) and ranked in
    Python with ``dig.graph.ranking`` so version numbers and module names count. With an empty
    query the newest decisions come first.
    """
    from dig.graph.ranking import query_terms, score_decision

    elements = GraphElements()
    cypher = """
    MATCH (node:Decision)
    OPTIONAL MATCH (node)-[:AFFECTS]->(m:Module)
    WITH node, collect(DISTINCT m.name) AS modules
    WHERE ($module IS NULL OR $module IN modules)
      AND ($status IS NULL OR node.status = $status)
      AND ($dtype IS NULL OR node.type = $dtype)
    RETURN node, modules
    LIMIT 5000
    """
    res = graph.query(cypher, params={"module": module, "status": status, "dtype": decision_type})

    words, versions = query_terms(query)
    has_query = bool(words or versions)
    scored: list[tuple[float, str, Any, list[str]]] = []
    for row in res.result_set or []:
        node = row[0]
        modules_list = list(row[1] or [])
        props = dict(getattr(node, "properties", {}))
        score = (
            score_decision(
                query,
                str(props.get("title", "")),
                str(props.get("summary", "")),
                modules_list,
                str(props.get("type", "")),
            )
            if has_query
            else 1.0
        )
        if has_query and score <= 0:
            continue
        scored.append((score, str(props.get("decided_at") or ""), node, modules_list))

    # Highest score first; ties go to the most recent decision.
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    if has_query and scored:
        # Drop incidental matches (a shared word like 'python') far below the best hit.
        cutoff = scored[0][0] * 0.15
        scored = [t for t in scored if t[0] >= cutoff]

    items: list[DecisionSearchResult] = []
    for score, _decided, node, modules_list in scored[:limit]:
        props = dict(getattr(node, "properties", {}))
        elements.nodes.append(node_to_graph_node(node))
        items.append(
            DecisionSearchResult(
                id=str(props.get("id", "")),
                title=str(props.get("title", "")),
                type=str(props.get("type", "")),
                status=str(props.get("status", "")),
                decided_at=props.get("decided_at"),
                modules=modules_list,
                score=round(score, 3),
            )
        )

    return QueryResult(data=items, graph_elements=elements)


def get_decision(graph: Any, decision_id: str) -> QueryResult[DecisionDetail | None]:
    """Retrieve complete decision with evidence, people, and sources."""
    elements = GraphElements()
    cypher = """
    MATCH (d:Decision {id: $id})
    OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(e:Evidence)
    OPTIONAL MATCH (p:Person)-[r:MADE]->(d)
    OPTIONAL MATCH (d)-[:DECIDED_IN]->(src)
    RETURN d,
           collect(DISTINCT e) AS evidence,
           collect(DISTINCT {person: p, role: r.role}) AS people,
           collect(DISTINCT src) AS sources
    """
    res = graph.query(cypher, params={"id": decision_id})
    if not res.result_set or not res.result_set[0][0]:
        return QueryResult(data=None, graph_elements=elements)

    row = res.result_set[0]
    d_node = row[0]
    d_props = dict(getattr(d_node, "properties", {}))
    g_d_node = node_to_graph_node(d_node)
    elements.nodes.append(g_d_node)

    # Process evidence
    evidence_items: list[EvidenceItem] = []
    raw_evidence = row[1] or []
    for ev in raw_evidence:
        if ev is None:
            continue
        ev_props = dict(getattr(ev, "properties", {}))
        g_ev_node = node_to_graph_node(ev)
        elements.nodes.append(g_ev_node)
        elements.edges.append(
            GraphEdge(
                id=f"{g_d_node.id}->{g_ev_node.id}:SUPPORTED_BY",
                source=g_d_node.id,
                target=g_ev_node.id,
                type="SUPPORTED_BY",
            )
        )
        evidence_items.append(
            EvidenceItem(
                id=str(ev_props.get("id", "")),
                kind=str(ev_props.get("kind", "")),
                source_id=str(ev_props.get("source_id", "")),
                quote=str(ev_props.get("quote", "")),
                url=str(ev_props.get("url", "")),
                author=str(ev_props.get("author", "")),
                ts=str(ev_props.get("ts", "")),
            )
        )

    # Process people
    people_items: list[PersonRole] = []
    raw_people = row[2] or []
    for entry in raw_people:
        if not entry:
            continue
        p_node = entry.get("person") if isinstance(entry, dict) else None
        role = entry.get("role", "proposer") if isinstance(entry, dict) else "proposer"
        if p_node:
            p_props = dict(getattr(p_node, "properties", {}))
            g_p_node = node_to_graph_node(p_node)
            elements.nodes.append(g_p_node)
            elements.edges.append(
                GraphEdge(
                    id=f"{g_p_node.id}->{g_d_node.id}:MADE",
                    source=g_p_node.id,
                    target=g_d_node.id,
                    type="MADE",
                    props={"role": role},
                )
            )
            people_items.append(PersonRole(login=str(p_props.get("login", "")), role=role))

    # Process sources
    source_urls: list[str] = []
    raw_sources = row[3] or []
    for src in raw_sources:
        if src is None:
            continue
        s_props = dict(getattr(src, "properties", {}))
        g_s_node = node_to_graph_node(src)
        elements.nodes.append(g_s_node)
        elements.edges.append(
            GraphEdge(
                id=f"{g_d_node.id}->{g_s_node.id}:DECIDED_IN",
                source=g_d_node.id,
                target=g_s_node.id,
                type="DECIDED_IN",
            )
        )
        if s_props.get("url"):
            source_urls.append(str(s_props["url"]))

    detail = DecisionDetail(
        id=str(d_props.get("id", "")),
        title=str(d_props.get("title", "")),
        summary=str(d_props.get("summary", "")),
        type=str(d_props.get("type", "")),
        status=str(d_props.get("status", "")),
        decided_at=d_props.get("decided_at"),
        valid_from=d_props.get("valid_from"),
        valid_to=d_props.get("valid_to"),
        confidence=float(d_props.get("confidence", 1.0)),
        evidence=evidence_items,
        people=people_items,
        sources=source_urls,
    )

    return QueryResult(data=detail, graph_elements=elements)


def get_lineage(graph: Any, decision_id: str) -> QueryResult[LineageResult]:
    """Retrieve decision lineage chain across SUPERSEDES and REVERSES edges."""
    elements = GraphElements()
    hops: list[LineageHop] = []
    seen_decisions: dict[str, DecisionSearchResult] = {}

    # Fetch root decision
    root_res = graph.query("MATCH (d:Decision {id: $id}) RETURN d", params={"id": decision_id})
    if not root_res.result_set or not root_res.result_set[0][0]:
        return QueryResult(
            data=LineageResult(root_id=decision_id, hops=[], decisions=[]),
            graph_elements=elements,
        )

    root_node = root_res.result_set[0][0]
    root_props = dict(getattr(root_node, "properties", {}))
    g_root = node_to_graph_node(root_node)
    elements.nodes.append(g_root)
    seen_decisions[decision_id] = DecisionSearchResult(
        id=decision_id,
        title=str(root_props.get("title", "")),
        type=str(root_props.get("type", "")),
        status=str(root_props.get("status", "")),
        decided_at=root_props.get("decided_at"),
        score=1.0,
    )

    # 1. Outgoing edges (e.g. root SUPERSEDES older)
    out_cypher = """
    MATCH (d:Decision {id: $id})-[r:SUPERSEDES|REVERSES]->(target:Decision)
    RETURN d, r, target
    """
    out_res = graph.query(out_cypher, params={"id": decision_id})
    if out_res.result_set:
        for row in out_res.result_set:
            _d_node, r_edge, t_node = row[0], row[1], row[2]
            g_t = node_to_graph_node(t_node)
            elements.nodes.append(g_t)
            g_edge = edge_to_graph_edge(r_edge, g_root.id, g_t.id)
            elements.edges.append(g_edge)

            t_props = dict(getattr(t_node, "properties", {}))
            t_id = str(t_props.get("id", ""))
            seen_decisions[t_id] = DecisionSearchResult(
                id=t_id,
                title=str(t_props.get("title", "")),
                type=str(t_props.get("type", "")),
                status=str(t_props.get("status", "")),
                decided_at=t_props.get("decided_at"),
                score=1.0,
            )
            hops.append(
                LineageHop(
                    decision_id=decision_id,
                    title=str(root_props.get("title", "")),
                    status=str(root_props.get("status", "")),
                    decided_at=root_props.get("decided_at"),
                    relation=getattr(r_edge, "relation", "SUPERSEDES"),
                    direction="outgoing",
                    target_id=t_id,
                )
            )

    # 2. Incoming edges (e.g. newer SUPERSEDES root)
    in_cypher = """
    MATCH (source:Decision)-[r:SUPERSEDES|REVERSES]->(d:Decision {id: $id})
    RETURN source, r, d
    """
    in_res = graph.query(in_cypher, params={"id": decision_id})
    if in_res.result_set:
        for row in in_res.result_set:
            s_node, r_edge, _d_node = row[0], row[1], row[2]
            g_s = node_to_graph_node(s_node)
            elements.nodes.append(g_s)
            g_edge = edge_to_graph_edge(r_edge, g_s.id, g_root.id)
            elements.edges.append(g_edge)

            s_props = dict(getattr(s_node, "properties", {}))
            s_id = str(s_props.get("id", ""))
            seen_decisions[s_id] = DecisionSearchResult(
                id=s_id,
                title=str(s_props.get("title", "")),
                type=str(s_props.get("type", "")),
                status=str(s_props.get("status", "")),
                decided_at=s_props.get("decided_at"),
                score=1.0,
            )
            hops.append(
                LineageHop(
                    decision_id=s_id,
                    title=str(s_props.get("title", "")),
                    status=str(s_props.get("status", "")),
                    decided_at=s_props.get("decided_at"),
                    relation=getattr(r_edge, "relation", "SUPERSEDES"),
                    direction="incoming",
                    target_id=decision_id,
                )
            )

    # Sort decisions chronologically
    sorted_decisions = sorted(
        seen_decisions.values(),
        key=lambda d: d.decided_at or "",
    )

    return QueryResult(
        data=LineageResult(
            root_id=decision_id,
            hops=hops,
            decisions=sorted_decisions,
        ),
        graph_elements=elements,
    )


def who_knows(graph: Any, module: str, limit: int = 5) -> QueryResult[list[WhoKnowsItem]]:
    """Query people with KNOWS expertise score on the specified module."""
    elements = GraphElements()
    items: list[WhoKnowsItem] = []

    cypher = """
    MATCH (p:Person)-[k:KNOWS]->(m:Module {name: $module})
    WHERE p.is_bot = false
    RETURN p, k, m, p.login AS login, k.score AS score, k.authored AS authored,
           k.reviewed AS reviewed, k.commented AS commented, k.last_active AS last_active
    ORDER BY k.score DESC LIMIT $limit
    """
    res = graph.query(cypher, params={"module": module, "limit": limit})
    if res.result_set:
        for row in res.result_set:
            p_node, k_edge, m_node = row[0], row[1], row[2]
            g_p = node_to_graph_node(p_node)
            g_m = node_to_graph_node(m_node)
            elements.nodes.append(g_p)
            elements.nodes.append(g_m)
            elements.edges.append(edge_to_graph_edge(k_edge, g_p.id, g_m.id))

            items.append(
                WhoKnowsItem(
                    login=str(row[3]),
                    score=float(row[4]),
                    authored=int(row[5] or 0),
                    reviewed=int(row[6] or 0),
                    commented=int(row[7] or 0),
                    last_active=row[8],
                )
            )

    return QueryResult(data=items, graph_elements=elements)


def impact_of(graph: Any, decision_id: str) -> QueryResult[ImpactResult]:
    """Analyze impact of a decision on modules, files, concepts, and releases."""
    elements = GraphElements()
    cypher = """
    MATCH (d:Decision {id: $id})
    OPTIONAL MATCH (d)-[a:AFFECTS]->(x)
    OPTIONAL MATCH (d)<-[dep:DEPENDS_ON]-(down:Decision)
    OPTIONAL MATCH (d)-[:DECIDED_IN]->(:PullRequest)-[:SHIPPED_IN]->(r:Release)
    RETURN d,
           collect(DISTINCT {node: x, label: labels(x)[0], name: coalesce(x.name, x.path)}) AS affected,
           collect(DISTINCT down) AS downstream,
           collect(DISTINCT r) AS releases
    """
    res = graph.query(cypher, params={"id": decision_id})
    if not res.result_set or not res.result_set[0][0]:
        return QueryResult(
            data=ImpactResult(decision_id=decision_id, affected=[], downstream=[], releases=[]),
            graph_elements=elements,
        )

    row = res.result_set[0]
    d_node = row[0]
    g_d = node_to_graph_node(d_node)
    elements.nodes.append(g_d)

    affected_items: list[dict[str, Any]] = []
    raw_affected = row[1] or []
    for item in raw_affected:
        if not item or not item.get("node"):
            continue
        x_node = item["node"]
        g_x = node_to_graph_node(x_node)
        elements.nodes.append(g_x)
        elements.edges.append(
            GraphEdge(
                id=f"{g_d.id}->{g_x.id}:AFFECTS",
                source=g_d.id,
                target=g_x.id,
                type="AFFECTS",
            )
        )
        affected_items.append({"label": item.get("label"), "name": item.get("name")})

    downstream_ids: list[str] = []
    raw_down = row[2] or []
    for down in raw_down:
        if down is None:
            continue
        g_down = node_to_graph_node(down)
        elements.nodes.append(g_down)
        elements.edges.append(
            GraphEdge(
                id=f"{g_down.id}->{g_d.id}:DEPENDS_ON",
                source=g_down.id,
                target=g_d.id,
                type="DEPENDS_ON",
            )
        )
        d_props = dict(getattr(down, "properties", {}))
        if d_props.get("id"):
            downstream_ids.append(str(d_props["id"]))

    release_tags: list[str] = []
    raw_rels = row[3] or []
    for rel in raw_rels:
        if rel is None:
            continue
        g_rel = node_to_graph_node(rel)
        elements.nodes.append(g_rel)
        r_props = dict(getattr(rel, "properties", {}))
        if r_props.get("tag"):
            release_tags.append(str(r_props["tag"]))

    return QueryResult(
        data=ImpactResult(
            decision_id=decision_id,
            affected=affected_items,
            downstream=downstream_ids,
            releases=release_tags,
        ),
        graph_elements=elements,
    )


def active_decisions_for_modules(
    graph: Any,
    modules: list[str],
) -> QueryResult[list[ActiveDecisionItem]]:
    """Retrieve active decisions that affect the specified modules (Decision Guard query)."""
    elements = GraphElements()
    items: list[ActiveDecisionItem] = []

    if not modules:
        return QueryResult(data=items, graph_elements=elements)

    cypher = """
    MATCH (d:Decision {status: 'active'})-[a:AFFECTS]->(m:Module)
    WHERE m.name IN $modules
    RETURN d, m, d.id AS id, d.title AS title, d.type AS type, d.summary AS summary,
           collect(DISTINCT m.name) AS modules
    """
    res = graph.query(cypher, params={"modules": modules})
    if res.result_set:
        for row in res.result_set:
            d_node, m_node = row[0], row[1]
            g_d = node_to_graph_node(d_node)
            g_m = node_to_graph_node(m_node)
            elements.nodes.append(g_d)
            elements.nodes.append(g_m)
            elements.edges.append(
                GraphEdge(
                    id=f"{g_d.id}->{g_m.id}:AFFECTS",
                    source=g_d.id,
                    target=g_m.id,
                    type="AFFECTS",
                )
            )

            d_props = dict(getattr(d_node, "properties", {}))
            modules_list = row[6] or []
            items.append(
                ActiveDecisionItem(
                    id=str(row[2] or d_props.get("id", "")),
                    title=str(row[3] or d_props.get("title", "")),
                    type=str(row[4] or d_props.get("type", "")),
                    summary=str(row[5] or d_props.get("summary", "")),
                    modules=modules_list,
                )
            )

    return QueryResult(data=items, graph_elements=elements)


def shortest_path(
    graph: Any,
    a_id: str,
    b_id: str,
) -> QueryResult[ShortestPathResult | None]:
    """Find shortest path between two nodes by uid, id, login, name, tag, or path.

    Uses directed FalkorDB shortestPath where possible, and networkx fallback
    for undirected multi-hop traversal.
    """
    elements = GraphElements()

    # Locate source and target nodes
    find_cypher = """
    MATCH (n)
    WHERE n.uid = $target OR n.id = $target OR n.login = $target
       OR n.name = $target OR n.tag = $target OR n.path = $target
    RETURN n LIMIT 1
    """
    res_a = graph.query(find_cypher, params={"target": a_id})
    res_b = graph.query(find_cypher, params={"target": b_id})

    if not res_a.result_set or not res_b.result_set:
        return QueryResult(data=None, graph_elements=elements)

    node_a = res_a.result_set[0][0]
    node_b = res_b.result_set[0][0]
    g_a = node_to_graph_node(node_a)
    g_b = node_to_graph_node(node_b)

    # 1. Try directed path A -> B in FalkorDB
    dir_cypher = """
    MATCH (a), (b)
    WHERE a.uid = $a_uid AND b.uid = $b_uid
    RETURN shortestPath((a)-[*..6]->(b)) AS p
    """
    try:
        p_res = graph.query(dir_cypher, params={"a_uid": g_a.id, "b_uid": g_b.id})
        if p_res.result_set and p_res.result_set[0][0]:
            path_obj = p_res.result_set[0][0]
            nodes = path_obj.nodes
            edges = path_obj.edges
            node_uids: list[str] = []
            edge_ids: list[str] = []
            for n in nodes:
                gn = node_to_graph_node(n)
                elements.nodes.append(gn)
                node_uids.append(gn.id)
            for e in edges:
                rel = getattr(e, "relation", "RELATED")
                edge_ids.append(rel)

            return QueryResult(
                data=ShortestPathResult(
                    source_id=g_a.id,
                    target_id=g_b.id,
                    length=len(edges),
                    path_nodes=node_uids,
                    path_edges=edge_ids,
                ),
                graph_elements=elements,
            )
    except Exception as exc:
        logger.debug("Directed shortestPath (A->B) skipped: %s", exc)

    # 2. Try directed path B -> A in FalkorDB
    try:
        p_res = graph.query(dir_cypher, params={"a_uid": g_b.id, "b_uid": g_a.id})
        if p_res.result_set and p_res.result_set[0][0]:
            path_obj = p_res.result_set[0][0]
            nodes = path_obj.nodes
            edges = path_obj.edges
            node_uids = []
            edge_ids = []
            for n in nodes:
                gn = node_to_graph_node(n)
                elements.nodes.append(gn)
                node_uids.append(gn.id)
            for e in edges:
                rel = getattr(e, "relation", "RELATED")
                edge_ids.append(rel)

            return QueryResult(
                data=ShortestPathResult(
                    source_id=g_b.id,
                    target_id=g_a.id,
                    length=len(edges),
                    path_nodes=node_uids,
                    path_edges=edge_ids,
                ),
                graph_elements=elements,
            )
    except Exception as exc:
        logger.debug("Directed shortestPath (B->A) skipped: %s", exc)

    # 3. Fallback to networkx undirected path over the graph
    # Export 6-hop neighborhood of a and b
    subgraph_cypher = """
    MATCH (n)-[r]-(m)
    RETURN n, r, m LIMIT 500
    """
    sub_res = graph.query(subgraph_cypher)
    if not sub_res.result_set:
        return QueryResult(data=None, graph_elements=elements)

    nx_g = nx.Graph()
    node_map: dict[str, GraphNode] = {}

    for row in sub_res.result_set:
        n, r, m = row[0], row[1], row[2]
        gn = node_to_graph_node(n)
        gm = node_to_graph_node(m)
        node_map[gn.id] = gn
        node_map[gm.id] = gm
        rel = getattr(r, "relation", "RELATED")
        nx_g.add_edge(gn.id, gm.id, relation=rel, edge_obj=r)

    if g_a.id in nx_g and g_b.id in nx_g and nx.has_path(nx_g, g_a.id, g_b.id):
        path_nodes = nx.shortest_path(nx_g, g_a.id, g_b.id)
        path_edges: list[str] = []
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            edge_data = nx_g.get_edge_data(u, v) or {}
            rel = edge_data.get("relation", "RELATED")
            path_edges.append(rel)
            elements.edges.append(GraphEdge(id=f"{u}->{v}:{rel}", source=u, target=v, type=rel))

        for nid in path_nodes:
            if nid in node_map:
                elements.nodes.append(node_map[nid])

        return QueryResult(
            data=ShortestPathResult(
                source_id=g_a.id,
                target_id=g_b.id,
                length=len(path_edges),
                path_nodes=path_nodes,
                path_edges=path_edges,
            ),
            graph_elements=elements,
        )

    return QueryResult(data=None, graph_elements=elements)


def run_demo_queries(graph_name: str = "dig_pallets_flask") -> list[dict[str, Any]]:
    """Run all core queries against the seed graph and report results."""
    graph = get_graph(graph_name)
    results: list[dict[str, Any]] = []

    # 1. search_decisions
    q_search = search_decisions(graph, "Python")
    results.append(
        {
            "query": "search_decisions",
            "params": "query='Python'",
            "rows": len(q_search.data),
            "nodes_touched": len(q_search.graph_elements.nodes),
        }
    )

    # 2. get_decision
    q_detail = get_decision(graph, "dec_drop_py36")
    results.append(
        {
            "query": "get_decision",
            "params": "id='dec_drop_py36'",
            "rows": 1 if q_detail.data else 0,
            "nodes_touched": len(q_detail.graph_elements.nodes),
        }
    )

    # 3. get_lineage
    q_lineage = get_lineage(graph, "dec_drop_py36")
    results.append(
        {
            "query": "get_lineage",
            "params": "id='dec_drop_py36'",
            "rows": len(q_lineage.data.hops),
            "nodes_touched": len(q_lineage.graph_elements.nodes),
        }
    )

    # 4. who_knows
    q_knows = who_knows(graph, "flask/app")
    results.append(
        {
            "query": "who_knows",
            "params": "module='flask/app'",
            "rows": len(q_knows.data),
            "nodes_touched": len(q_knows.graph_elements.nodes),
        }
    )

    # 5. impact_of
    q_impact = impact_of(graph, "dec_drop_py36")
    results.append(
        {
            "query": "impact_of",
            "params": "id='dec_drop_py36'",
            "rows": len(q_impact.data.affected),
            "nodes_touched": len(q_impact.graph_elements.nodes),
        }
    )

    # 6. active_decisions_for_modules
    q_active = active_decisions_for_modules(graph, ["flask/app", "flask/compat"])
    results.append(
        {
            "query": "active_decisions_for_modules",
            "params": "modules=['flask/app', 'flask/compat']",
            "rows": len(q_active.data),
            "nodes_touched": len(q_active.graph_elements.nodes),
        }
    )

    # 7. shortest_path
    q_path = shortest_path(graph, "davidism", "flask/views")
    results.append(
        {
            "query": "shortest_path",
            "params": "a='davidism', b='flask/views'",
            "rows": 1 if q_path.data else 0,
            "nodes_touched": len(q_path.graph_elements.nodes),
        }
    )

    return results


if __name__ == "__main__":
    import sys

    if "--demo" in sys.argv:
        print("\n=== FalkorDB Core Queries Demo ===")
        demo_results = run_demo_queries()
        header = f"{'Query Name':<30} | {'Parameters':<35} | {'Rows':<6} | {'Nodes':<6}"
        print("-" * len(header))
        print(header)
        print("-" * len(header))
        for r in demo_results:
            print(
                f"{r['query']:<30} | {r['params']:<35} | {r['rows']:<6} | {r['nodes_touched']:<6}"
            )
        print("-" * len(header))
