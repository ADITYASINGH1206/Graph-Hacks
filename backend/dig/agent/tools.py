"""Tool definitions and registry for Agent loop and FastMCP server."""

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from dig.graph.algos import central_people_alg
from dig.graph.client import get_graph
from dig.graph.models import GraphElements
from dig.graph.queries import (
    get_decision,
    get_lineage,
    impact_of,
    node_to_graph_node,
    search_decisions,
    shortest_path,
    who_knows,
)


class ToolMeta(BaseModel):
    """Metadata and schema for an agent tool."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters_schema: dict[str, Any]


class ToolRegistry:
    """Central registry of tools used by both the LLM agent and FastMCP server."""

    def __init__(self):
        self.tools: dict[str, ToolMeta] = {}

    def register(self, name: str, description: str):
        """Decorator to register a tool function with its JSON schema."""

        def decorator(fn: Callable[..., Any]):
            sig = inspect.signature(fn)
            properties: dict[str, Any] = {}
            required: list[str] = []

            type_map = {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean",
                list: "array",
                dict: "object",
            }

            for param_name, param in sig.parameters.items():
                if param_name in ("graph", "self"):
                    continue
                annotation = param.annotation
                ptype = "string"
                if annotation in type_map:
                    ptype = type_map[annotation]
                elif hasattr(annotation, "__origin__"):
                    if annotation.__origin__ is list:
                        ptype = "array"

                properties[param_name] = {
                    "type": ptype,
                    "description": f"Parameter {param_name}",
                }
                if param.default is inspect.Parameter.empty:
                    required.append(param_name)

            schema = {
                "type": "object",
                "properties": properties,
                "required": required,
            }

            meta = ToolMeta(
                name=name,
                description=description,
                func=fn,
                parameters_schema=schema,
            )
            self.tools[name] = meta
            return fn

        return decorator

    def get(self, name: str) -> ToolMeta | None:
        return self.tools.get(name)

    def list_tools(self) -> list[ToolMeta]:
        return list(self.tools.values())


registry = ToolRegistry()


# ---------------------------------------------------------------------------
# Tool Catalogue Implementations
# ---------------------------------------------------------------------------


@registry.register(
    name="search_decisions",
    description="Search decisions in the repository by text query, module, decision type, or status.",
)
def tool_search_decisions(
    query: str = "",
    module: str | None = None,
    decision_type: str | None = None,
    status: str | None = None,
    limit: int = 8,
    graph: Any | None = None,
) -> dict[str, Any]:
    g = graph or get_graph()
    res = search_decisions(
        g,
        query=query,
        module=module,
        decision_type=decision_type,
        status=status,
        limit=limit,
    )
    return {
        "data": [d.model_dump() for d in res.data],
        "graph_elements": res.graph_elements.model_dump(),
        "summary": f"Found {len(res.data)} decisions matching '{query}'.",
    }


@registry.register(
    name="get_decision",
    description="Retrieve details for a specific decision including evidence quotes, deciders, and sources.",
)
def tool_get_decision(
    decision_id: str,
    graph: Any | None = None,
) -> dict[str, Any]:
    g = graph or get_graph()
    res = get_decision(g, decision_id)
    data = res.data.model_dump() if res.data else None
    summary = f"Retrieved decision {decision_id}: {res.data.title}" if res.data else f"Decision {decision_id} not found."
    return {
        "data": data,
        "graph_elements": res.graph_elements.model_dump(),
        "summary": summary,
    }


@registry.register(
    name="trace_to_source",
    description="Trace a decision back to its verified evidence items with URLs, quotes, and authors.",
)
def tool_trace_to_source(
    decision_id: str,
    graph: Any | None = None,
) -> dict[str, Any]:
    g = graph or get_graph()
    res = get_decision(g, decision_id)
    if not res.data:
        return {
            "data": [],
            "graph_elements": GraphElements().model_dump(),
            "summary": f"No source evidence found for {decision_id}.",
        }

    evidence_list = [ev.model_dump() for ev in res.data.evidence]
    return {
        "data": evidence_list,
        "graph_elements": res.graph_elements.model_dump(),
        "summary": f"Traced {len(evidence_list)} evidence quotes for decision {decision_id}.",
    }


@registry.register(
    name="decision_lineage",
    description="Traverse the chronological chain of SUPERSEDES and REVERSES decisions starting from a decision.",
)
def tool_decision_lineage(
    decision_id: str,
    graph: Any | None = None,
) -> dict[str, Any]:
    g = graph or get_graph()
    res = get_lineage(g, decision_id)
    return {
        "data": res.data.model_dump(),
        "graph_elements": res.graph_elements.model_dump(),
        "summary": f"Found {len(res.data.hops)} lineage hops for {decision_id}.",
    }


@registry.register(
    name="who_knows",
    description="Identify people with KNOWS expertise score on a module, based on authored PRs, reviews, and comments.",
)
def tool_who_knows(
    module: str,
    limit: int = 5,
    graph: Any | None = None,
) -> dict[str, Any]:
    g = graph or get_graph()
    res = who_knows(g, module=module, limit=limit)
    return {
        "data": [p.model_dump() for p in res.data],
        "graph_elements": res.graph_elements.model_dump(),
        "summary": f"Found {len(res.data)} experts for module '{module}'.",
    }


@registry.register(
    name="who_decided",
    description="Identify the engineers who made, proposed, or approved a decision.",
)
def tool_who_decided(
    decision_id: str,
    graph: Any | None = None,
) -> dict[str, Any]:
    g = graph or get_graph()
    res = get_decision(g, decision_id)
    if not res.data:
        return {
            "data": [],
            "graph_elements": GraphElements().model_dump(),
            "summary": f"Decision {decision_id} not found.",
        }
    people = [p.model_dump() for p in res.data.people]
    return {
        "data": people,
        "graph_elements": res.graph_elements.model_dump(),
        "summary": f"Found {len(people)} engineers who decided {decision_id}.",
    }


@registry.register(
    name="impact_of",
    description="Analyze the impact of a decision: affected modules, files, downstream decisions, and release tags.",
)
def tool_impact_of(
    decision_id: str,
    graph: Any | None = None,
) -> dict[str, Any]:
    g = graph or get_graph()
    res = impact_of(g, decision_id)
    return {
        "data": res.data.model_dump(),
        "graph_elements": res.graph_elements.model_dump(),
        "summary": f"Analyzed impact for {decision_id}: {len(res.data.affected)} components affected.",
    }


@registry.register(
    name="find_path",
    description="Find the shortest relationship path between two entities in the repository graph.",
)
def tool_find_path(
    a_id: str,
    b_id: str,
    graph: Any | None = None,
) -> dict[str, Any]:
    g = graph or get_graph()
    res = shortest_path(g, a_id=a_id, b_id=b_id)
    data = res.data.model_dump() if res.data else None
    summary = f"Path between {a_id} and {b_id}: {res.data.length} hops." if res.data else f"No path found between {a_id} and {b_id}."
    return {
        "data": data,
        "graph_elements": res.graph_elements.model_dump(),
        "summary": summary,
    }


@registry.register(
    name="central_people",
    description="Rank the most central and influential engineers across decisions and modules using PageRank.",
)
def tool_central_people(
    scope: str = "all",
    limit: int = 5,
    graph: Any | None = None,
) -> dict[str, Any]:
    g = graph or get_graph()
    ranked, elements = central_people_alg(g, scope=scope, limit=limit)
    return {
        "data": ranked,
        "graph_elements": elements.model_dump(),
        "summary": f"Top {len(ranked)} central people (scope: {scope}).",
    }


@registry.register(
    name="recent_changes",
    description="Fetch decisions created or modified since a given ISO date.",
)
def tool_recent_changes(
    since: str,
    limit: int = 10,
    graph: Any | None = None,
) -> dict[str, Any]:
    g = graph or get_graph()
    elements = GraphElements()
    cypher = """
    MATCH (d:Decision)
    WHERE d.decided_at >= $since OR d.valid_from >= $since
    RETURN d
    ORDER BY d.decided_at DESC LIMIT $limit
    """
    res = g.query(cypher, params={"since": since, "limit": limit})
    items = []
    if res.result_set:
        for row in res.result_set:
            d_node = row[0]
            gn = node_to_graph_node(d_node)
            elements.nodes.append(gn)
            props = dict(d_node.properties)
            items.append({
                "id": props.get("id"),
                "title": props.get("title"),
                "status": props.get("status"),
                "decided_at": props.get("decided_at"),
            })

    return {
        "data": items,
        "graph_elements": elements.model_dump(),
        "summary": f"Found {len(items)} decisions since {since}.",
    }


# Automatically load extended tool modules so their @registry.register decorators run
import dig.agent.adr  # noqa: E402, F401
import dig.agent.guard  # noqa: E402, F401
import dig.agent.memory  # noqa: E402, F401
