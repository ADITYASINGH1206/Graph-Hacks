"""Architectural Decision Record (ADR) generator."""

from typing import Any

from dig.agent.tools import registry
from dig.graph.client import get_graph
from dig.graph.queries import get_decision, impact_of


@registry.register(
    name="draft_adr",
    description="Generate a complete Markdown Architectural Decision Record (ADR) with context, consequences, and evidence links.",
)
def tool_draft_adr(
    decision_id: str,
    graph: Any | None = None,
) -> dict[str, Any]:
    """Format an Architectural Decision Record from graph provenance data."""
    g = graph or get_graph()
    dec_res = get_decision(g, decision_id)
    if not dec_res.data:
        return {
            "data": None,
            "graph_elements": dec_res.graph_elements.model_dump(),
            "summary": f"Decision {decision_id} not found.",
        }

    dec = dec_res.data
    impact_res = impact_of(g, decision_id)
    impact = impact_res.data

    people_lines = []
    for p in dec.people:
        p_name = getattr(p, "name", None) or p.login
        people_lines.append(f"- @{p.login} ({p_name}) - {p.role}")
    people_str = "\n".join(people_lines) if people_lines else "- Maintainers"

    evidence_lines = []
    for ev in dec.evidence:
        evidence_lines.append(f"> \"{ev.quote}\"\n> — [{ev.author}]({ev.url})")
    evidence_str = "\n\n".join(evidence_lines) if evidence_lines else "None recorded."

    affected_modules = [a["name"] for a in (impact.affected if impact else []) if a.get("label") == "Module"]
    affected_files = [a["name"] for a in (impact.affected if impact else []) if a.get("label") == "File"]

    modules_str = ", ".join(f"`{m}`" for m in affected_modules) or "None"
    files_str = ", ".join(f"`{f}`" for f in affected_files) or "None"

    downstream_lines = []
    if impact and impact.downstream:
        for ds in impact.downstream:
            downstream_lines.append(f"- [{ds.relation}] `{ds.id}`: {ds.title}")
    downstream_str = "\n".join(downstream_lines) if downstream_lines else "- None"

    adr_markdown = f"""# ADR-{dec.id}: {dec.title}

## Status
**{dec.status.upper()}** (Decided: {dec.decided_at or 'Unknown'})

## Deciders
{people_str}

## Context
{dec.summary}

## Decision
The project decided to classify this change as `{dec.type}` with confidence {dec.confidence}.

## Evidence and Provenance
{evidence_str}

## Consequences
- **Affected Modules**: {modules_str}
- **Affected Files**: {files_str}
- **Downstream Impact**:
{downstream_str}
"""

    return {
        "data": {
            "decision_id": dec.id,
            "title": dec.title,
            "markdown": adr_markdown,
        },
        "graph_elements": dec_res.graph_elements.model_dump(),
        "summary": f"Generated ADR for decision {decision_id}.",
    }
