"""Pydantic API request and response models matching docs/API_CONTRACT.md."""

from typing import Any

from dig.agent.verifier import Citation
from dig.graph.models import GraphElements
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check status and graph entity counts."""

    ok: bool = True
    graph: str
    counts: dict[str, int]
    last_synced: str | None = None


class AskRequest(BaseModel):
    """Payload for POST /ask SSE streaming query."""

    question: str
    user_id: str = "anonymous"
    session_id: str | None = None


class GuardRequest(BaseModel):
    """Payload for POST /guard proposal conflict checking."""

    description: str
    paths: list[str] = Field(default_factory=list)


class ConflictItem(BaseModel):
    decision_id: str
    title: str
    status: str
    confidence: float
    why: str
    evidence: list[Citation] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)


class AlignmentItem(BaseModel):
    decision_id: str
    title: str
    why: str


class ReversedBeforeItem(BaseModel):
    decision_id: str
    title: str
    why: str


class GuardResponse(BaseModel):
    conflicts: list[ConflictItem] = Field(default_factory=list)
    alignments: list[AlignmentItem] = Field(default_factory=list)
    reversed_before: list[ReversedBeforeItem] = Field(default_factory=list)
    graph: GraphElements = Field(default_factory=GraphElements)


class DecisionTimelineItem(BaseModel):
    id: str
    title: str
    type: str
    status: str
    decided_at: str | None = None
    modules: list[str] = Field(default_factory=list)
    confidence: float = 1.0


class DecisionsListResponse(BaseModel):
    items: list[DecisionTimelineItem]


class DecisionDetailResponse(BaseModel):
    decision: dict[str, Any]
    evidence: list[Citation] = Field(default_factory=list)
    people: list[dict[str, Any]] = Field(default_factory=list)
    lineage: GraphElements = Field(default_factory=GraphElements)
    impact: dict[str, Any] = Field(default_factory=dict)
    stale: bool = False


class PersonModuleItem(BaseModel):
    name: str
    score: float


class PersonDecisionItem(BaseModel):
    id: str
    title: str
    role: str


class PersonDetailResponse(BaseModel):
    login: str
    modules: list[PersonModuleItem] = Field(default_factory=list)
    decisions: list[PersonDecisionItem] = Field(default_factory=list)


class SyncResponse(BaseModel):
    started: bool = True
