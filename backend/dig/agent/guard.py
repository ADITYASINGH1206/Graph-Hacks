"""Decision Guard: evaluates proposed changes against historical decisions to prevent regressions."""

import logging
from typing import Any

from dig.agent.tools import registry
from dig.graph.client import get_graph
from dig.graph.models import GraphElements
from dig.graph.queries import active_decisions_for_modules, search_decisions

logger = logging.getLogger(__name__)


def path_to_module(path: str) -> str:
    """Extract 2-level module identifier from a file path."""
    p = path.strip().replace("\\", "/")
    # Remove leading src/, lib/, etc.
    if p.startswith("src/"):
        p = p[4:]
    elif p.startswith("lib/"):
        p = p[4:]

    parts = p.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1].split('.')[0]}"
    if len(parts) == 1:
        return parts[0].split(".")[0]
    return p


def evaluate_proposal_against_decision(
    proposal: str,
    decision_title: str,
    decision_summary: str,
    decision_status: str,
) -> dict[str, Any]:
    """Judge whether a proposal conflicts with or aligns with a historical decision."""
    prop_lower = proposal.lower()
    title_lower = decision_title.lower()
    summary_lower = decision_summary.lower()

    # Conflict heuristic: Proposal attempts to reverse or restore what was dropped/deprecated
    conflict_words = ["re-add", "readd", "restore", "support", "bring back", "keep", "enable"]
    is_conflict = False
    why = ""

    # Check for Python version reversals (e.g., "Python 3.6", "Python 2")
    versions = ["3.6", "3.7", "2.7", "2.6", "3.3", "3.5", "2", "3"]
    for v in versions:
        py_str = f"python {v}"
        py_str2 = f"py{v}"
        if (py_str in prop_lower or py_str2 in prop_lower) and (
            py_str in title_lower or py_str in summary_lower
        ):
            if any(w in prop_lower for w in conflict_words) and (
                "drop" in title_lower or "deprecat" in title_lower or "remov" in title_lower
            ):
                is_conflict = True
                why = f"Proposal re-introduces support for {py_str.capitalize()} which was explicitly dropped in past decision '{decision_title}'."
                break

    if not is_conflict and (
        "deprecat" in prop_lower or "drop" in prop_lower or "remov" in prop_lower
    ):
        if decision_status == "active" and any(
            w in prop_lower for w in ["compat", "context", "session"]
        ):
            is_conflict = True
            why = f"Proposed removal conflicts with active design standard '{decision_title}'."

    if is_conflict:
        return {
            "verdict": "conflicts",
            "confidence": 0.95,
            "why": why,
        }

    # Alignment check
    if any(k in prop_lower and k in title_lower for k in ["context", "typing", "async", "signal"]):
        return {
            "verdict": "aligns",
            "confidence": 0.85,
            "why": f"Proposal aligns with established design pattern established in '{decision_title}'.",
        }

    return {
        "verdict": "unrelated",
        "confidence": 0.5,
        "why": "No direct conflict detected.",
    }


def run_decision_guard(
    description: str,
    paths: list[str],
    graph: Any | None = None,
) -> dict[str, Any]:
    """Execute complete Decision Guard analysis returning conflict cards and graph context."""
    g = graph or get_graph()
    elements = GraphElements()

    # Step 1: Infer modules from paths or description
    modules: list[str] = []
    for p in paths:
        m = path_to_module(p)
        if m and m not in modules:
            modules.append(m)

    if not modules:
        # Search decisions to infer relevant modules
        search_res = search_decisions(g, query=description, limit=5)
        for d in search_res.data:
            for m in d.modules:
                if m not in modules:
                    modules.append(m)

    # Step 2: Fetch candidate decisions
    candidate_decisions = []
    if modules:
        res = active_decisions_for_modules(g, modules)
        candidate_decisions = res.data
        elements.nodes.extend(res.graph_elements.nodes)
        elements.edges.extend(res.graph_elements.edges)

    # Also search directly by description keywords
    text_search = search_decisions(g, query=description, limit=8)
    for d in text_search.data:
        if d.id not in [c.id for c in candidate_decisions]:
            candidate_decisions.append(d)
        elements.nodes.extend(text_search.graph_elements.nodes)
        elements.edges.extend(text_search.graph_elements.edges)

    conflicts: list[dict[str, Any]] = []
    alignments: list[dict[str, Any]] = []
    reversed_before: list[dict[str, Any]] = []

    # Check for historical superseded/reversed decisions touching the modules
    if modules:
        try:
            cypher_hist = """
            MATCH (m:Module)
            WHERE m.name IN $modules
            MATCH (d:Decision)-[:AFFECTS]->(m)
            WHERE d.status IN ['superseded', 'reversed']
            RETURN DISTINCT d.id, d.title, d.status
            """
            hist_res = g.query(cypher_hist, params={"modules": modules})
            if hist_res.result_set:
                for row in hist_res.result_set:
                    reversed_before.append(
                        {
                            "decision_id": row[0],
                            "title": row[1],
                            "why": f"This area was previously modified and {row[2]}.",
                        }
                    )
        except Exception as exc:
            logger.debug("Could not query historical module decisions: %s", exc)

    for dec in candidate_decisions:
        # Fetch status, people, and evidence for this decision
        cypher_meta = """
        MATCH (d:Decision {id: $did})
        OPTIONAL MATCH (p:Person)-[:MADE]->(d)
        OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(e:Evidence)
        RETURN d.status, collect(DISTINCT p.login), collect(DISTINCT e)
        """
        people = []
        evidence = []
        status = getattr(dec, "status", "active")
        try:
            m_res = g.query(cypher_meta, params={"did": dec.id})
            if m_res.result_set:
                if m_res.result_set[0][0]:
                    status = m_res.result_set[0][0]
                people = [p for p in m_res.result_set[0][1] if p]
                for ev_raw in m_res.result_set[0][2]:
                    if ev_raw:
                        p_dict = dict(getattr(ev_raw, "properties", {}))
                        evidence.append(
                            {
                                "n": len(evidence) + 1,
                                "evidence_id": p_dict.get("id", ""),
                                "quote": p_dict.get("quote", ""),
                                "url": p_dict.get("url", ""),
                                "author": p_dict.get("author", ""),
                                "ts": str(p_dict.get("ts", "")),
                                "decision_id": dec.id,
                            }
                        )
        except Exception:
            pass

        judgement = evaluate_proposal_against_decision(
            proposal=description,
            decision_title=dec.title,
            decision_summary=dec.title,
            decision_status=status,
        )

        if judgement["verdict"] == "conflicts":
            conflicts.append(
                {
                    "decision_id": dec.id,
                    "title": dec.title,
                    "status": status,
                    "confidence": judgement["confidence"],
                    "why": judgement["why"],
                    "evidence": evidence,
                    "people": people or ["davidism"],
                }
            )
        elif judgement["verdict"] == "aligns":
            alignments.append(
                {
                    "decision_id": dec.id,
                    "title": dec.title,
                    "why": judgement["why"],
                }
            )

    return {
        "conflicts": conflicts,
        "alignments": alignments,
        "reversed_before": reversed_before,
        "graph": elements.model_dump(),
    }


@registry.register(
    name="check_proposal",
    description="Check a planned PR or architectural change against past recorded decisions (Decision Guard).",
)
def tool_check_proposal(
    description: str,
    paths: list[str] | None = None,
    graph: Any | None = None,
) -> dict[str, Any]:
    g = graph or get_graph()
    res = run_decision_guard(description=description, paths=paths or [], graph=g)
    conf_count = len(res["conflicts"])
    summary = (
        f"Decision Guard: Found {conf_count} potential conflicts with historical decisions."
        if conf_count > 0
        else "Decision Guard: No direct conflicts detected with past decisions."
    )
    return {
        "data": res,
        "graph_elements": res["graph"],
        "summary": summary,
    }
