"""Pydantic data models for graph elements and query outputs."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """A node representation for UI visualization and graph traversal."""

    id: str = Field(description="Node uid e.g. Label:key")
    label: str
    title: str
    props: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """A directed edge representation between two GraphNodes."""

    id: str = Field(description="Edge id e.g. source->target:TYPE")
    source: str = Field(description="Source node uid")
    target: str = Field(description="Target node uid")
    type: str = Field(description="Relationship type")
    props: dict[str, Any] = Field(default_factory=dict)


class GraphElements(BaseModel):
    """Collection of nodes and edges touched by a query or operation."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

    def merge(self, other: "GraphElements") -> "GraphElements":
        """Merge elements avoiding duplicates by id."""
        node_ids = {n.id for n in self.nodes}
        edge_ids = {e.id for e in self.edges}
        merged_nodes = list(self.nodes)
        merged_edges = list(self.edges)
        for n in other.nodes:
            if n.id not in node_ids:
                merged_nodes.append(n)
                node_ids.add(n.id)
        for e in other.edges:
            if e.id not in edge_ids:
                merged_edges.append(e)
                edge_ids.add(e.id)
        return GraphElements(nodes=merged_nodes, edges=merged_edges)


class Citation(BaseModel):
    """Citation referencing verified source evidence."""

    n: int = 1
    evidence_id: str
    quote: str
    url: str
    author: str
    ts: str
    decision_id: str | None = None


class DecisionSearchResult(BaseModel):
    """Single item returned from search_decisions."""

    id: str
    title: str
    type: str
    status: str
    decided_at: str | None = None
    modules: list[str] = Field(default_factory=list)
    score: float = 0.0


class PersonRole(BaseModel):
    """Person and their role in a decision."""

    login: str
    role: str = "proposer"


class EvidenceItem(BaseModel):
    """Evidence quote linked to a decision."""

    id: str
    kind: str
    source_id: str
    quote: str
    url: str
    author: str
    ts: str


class DecisionDetail(BaseModel):
    """Detailed information for a single decision."""

    id: str
    title: str
    summary: str
    type: str
    status: str
    decided_at: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    confidence: float = 1.0
    evidence: list[EvidenceItem] = Field(default_factory=list)
    people: list[PersonRole] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class LineageHop(BaseModel):
    """A step in a decision lineage chain."""

    decision_id: str
    title: str
    status: str
    decided_at: str | None = None
    relation: str  # SUPERSEDES, REVERSES, etc.
    direction: str  # 'outgoing' or 'incoming'
    target_id: str


class LineageResult(BaseModel):
    """Lineage result containing chain of decisions."""

    root_id: str
    hops: list[LineageHop] = Field(default_factory=list)
    decisions: list[DecisionSearchResult] = Field(default_factory=list)


class WhoKnowsItem(BaseModel):
    """Expertise details for a person on a module."""

    login: str
    score: float
    authored: int = 0
    reviewed: int = 0
    commented: int = 0
    last_active: str | None = None


class ImpactResult(BaseModel):
    """Impact analysis of a decision on modules, files, and downstream decisions."""

    decision_id: str
    affected: list[dict[str, Any]] = Field(default_factory=list)
    downstream: list[str] = Field(default_factory=list)
    releases: list[str] = Field(default_factory=list)


class ActiveDecisionItem(BaseModel):
    """Active decision affecting a module."""

    id: str
    title: str
    type: str
    summary: str
    modules: list[str] = Field(default_factory=list)


class ShortestPathResult(BaseModel):
    """Shortest path between two nodes."""

    source_id: str
    target_id: str
    length: int
    path_nodes: list[str] = Field(default_factory=list)
    path_edges: list[str] = Field(default_factory=list)


T = TypeVar("T")


class QueryResult(BaseModel, Generic[T]):
    """Wrapper returning typed data payload alongside touched graph elements."""

    data: T
    graph_elements: GraphElements = Field(default_factory=GraphElements)
