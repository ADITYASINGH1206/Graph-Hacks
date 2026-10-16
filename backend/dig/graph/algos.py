"""Graph algorithms: PageRank and centrality rankings over exported subgraphs using networkx.

Architecture note: Native FalkorDB algo.pageRank is restricted to a single relationship type.
For central_people, we export the heterogeneous Person-MADE->Decision and Person-KNOWS->Module
subgraph and compute PageRank in networkx to rank overall engineering influence.
"""

import logging
from typing import Any

import networkx as nx

from dig.graph.models import GraphElements, GraphNode
from dig.graph.queries import node_to_graph_node

logger = logging.getLogger(__name__)


def central_people_alg(
    graph: Any,
    scope: str = "all",
    limit: int = 5,
) -> tuple[list[dict[str, Any]], GraphElements]:
    """Calculate PageRank centrality of people across decisions and modules using networkx."""
    elements = GraphElements()
    nx_g = nx.DiGraph()
    person_nodes: dict[str, GraphNode] = {}

    if scope == "all" or not scope:
        # 1. Person -> Decision (MADE)
        cypher = """
        MATCH (p:Person)-[r:MADE]->(d:Decision)
        WHERE p.is_bot = false
        RETURN p, d
        """
        for row in graph.query(cypher).result_set:
            p_node, d_node = row[0], row[1]
            gp = node_to_graph_node(p_node)
            gd = node_to_graph_node(d_node)
            person_nodes[gp.props.get("login", gp.id)] = gp
            elements.nodes.append(gp)
            elements.nodes.append(gd)
            nx_g.add_edge(gp.props.get("login", gp.id), gd.id, weight=2.0)
            # Mutual edge for influence flow
            nx_g.add_edge(gd.id, gp.props.get("login", gp.id), weight=1.0)

        # 2. Person -> Module (KNOWS)
        cypher_knows = """
        MATCH (p:Person)-[k:KNOWS]->(m:Module)
        WHERE p.is_bot = false
        RETURN p, m, k.score
        """
        for row in graph.query(cypher_knows).result_set:
            p_node, m_node, score = row[0], row[1], float(row[2] or 1.0)
            gp = node_to_graph_node(p_node)
            gm = node_to_graph_node(m_node)
            person_nodes[gp.props.get("login", gp.id)] = gp
            elements.nodes.append(gp)
            elements.nodes.append(gm)
            nx_g.add_edge(gp.props.get("login", gp.id), gm.id, weight=score)
            nx_g.add_edge(gm.id, gp.props.get("login", gp.id), weight=score * 0.5)

    else:
        # Module-scoped centrality
        cypher_mod = """
        MATCH (p:Person)-[k:KNOWS]->(m:Module {name: $mod})
        WHERE p.is_bot = false
        OPTIONAL MATCH (p)-[r:MADE]->(d:Decision)-[:AFFECTS]->(m)
        RETURN p, m, k.score, d
        """
        for row in graph.query(cypher_mod, params={"mod": scope}).result_set:
            p_node, m_node, score, d_node = row[0], row[1], float(row[2] or 1.0), row[3]
            gp = node_to_graph_node(p_node)
            gm = node_to_graph_node(m_node)
            person_nodes[gp.props.get("login", gp.id)] = gp
            elements.nodes.append(gp)
            elements.nodes.append(gm)
            nx_g.add_edge(gp.props.get("login", gp.id), gm.id, weight=score)
            if d_node:
                gd = node_to_graph_node(d_node)
                elements.nodes.append(gd)
                nx_g.add_edge(gp.props.get("login", gp.id), gd.id, weight=2.0)

    if not nx_g or len(nx_g) == 0:
        return [], elements

    try:
        pagerank = nx.pagerank(nx_g, alpha=0.85, max_iter=100)
    except Exception as exc:
        logger.warning("PageRank calculation fallback to degree centrality: %s", exc)
        pagerank = nx.degree_centrality(nx_g)

    # Filter only person logins
    ranked_people = []
    for login in person_nodes:
        score = pagerank.get(login, 0.0)
        ranked_people.append({"login": login, "score": round(score, 4)})

    ranked_people.sort(key=lambda x: x["score"], reverse=True)
    results = ranked_people[:limit]
    for idx, item in enumerate(results, start=1):
        item["rank"] = idx

    return results, elements
