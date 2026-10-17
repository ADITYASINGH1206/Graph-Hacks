"""Tests for Decision Guard, draft_adr, and cross-session memory graph."""

import pytest
from dig.agent.adr import tool_draft_adr
from dig.agent.guard import path_to_module, run_decision_guard
from dig.agent.memory import pin_decision, recall_findings, record_finding
from dig.graph.client import get_graph
from scripts.seed_demo_graph import seed_demo_graph


@pytest.fixture(scope="module", autouse=True)
def setup_guard_test_graph():
    """Ensure default test graph is seeded."""
    graph = get_graph()
    seed_demo_graph(graph=graph)


def test_path_to_module_mapping():
    """Verify module mapping logic."""
    assert path_to_module("src/flask/compat.py") == "flask/compat"
    assert path_to_module("flask/app.py") == "flask/app"
    assert path_to_module("lib/flask/ctx.py") == "flask/ctx"


def test_decision_guard_detects_conflict():
    """Test Decision Guard identifying conflict with an active decision."""
    proposal = (
        "We should restore and re-add Python 3.6 compatibility helpers to avoid breaking old users."
    )
    paths = ["src/flask/compat.py"]

    res = run_decision_guard(description=proposal, paths=paths)
    conflicts = res["conflicts"]
    assert len(conflicts) >= 1
    conflict = conflicts[0]
    assert conflict["decision_id"] == "dec_drop_py36"
    assert conflict["status"] == "active"
    assert "davidism" in conflict["people"]
    assert len(conflict["evidence"]) >= 1
    assert "Python 3.6" in conflict["why"] or "re-introduces" in conflict["why"]


def test_decision_guard_reversed_before():
    """Test Decision Guard reporting previously superseded/reversed history."""
    proposal = "We want to modify compat layer"
    paths = ["src/flask/compat.py"]

    res = run_decision_guard(description=proposal, paths=paths)
    reversed_items = res["reversed_before"]
    assert len(reversed_items) >= 1
    ids = [item["decision_id"] for item in reversed_items]
    assert "dec_drop_py2" in ids


def test_draft_adr_generation():
    """Test tool_draft_adr generates structured Markdown with provenance."""
    res = tool_draft_adr("dec_drop_py36")
    data = res["data"]
    assert data is not None
    assert data["decision_id"] == "dec_drop_py36"
    md = data["markdown"]
    assert "# ADR-dec_drop_py36: Drop Python 3.6 support" in md
    assert "## Status" in md
    assert "ACTIVE" in md
    assert "@davidism" in md
    assert "## Evidence and Provenance" in md
    assert "https://github.com/pallets/flask/pull/4400" in md


def test_memory_graph_lifecycle():
    """Test recording, recalling, and pinning findings in FalkorDB memory graph."""
    user_id = "test_user_42"
    session_id = "sess_p10_test"

    # 1. Record finding
    record_finding(
        user_id=user_id,
        session_id=session_id,
        question_text="Why did we drop Python 3.6?",
        summary="Python 3.6 reached EOL and was removed in PR #4400.",
        decision_ids=["dec_drop_py36"],
    )

    # 2. Recall finding
    recalled = recall_findings(user_id=user_id, topic="Python 3.6", limit=3)
    assert len(recalled) >= 1
    assert "dec_drop_py36" in recalled[0]["decision_ids"]
    assert "Python 3.6 reached EOL" in recalled[0]["summary"]

    # 3. Pin decision
    pin_res = pin_decision(
        user_id=user_id, decision_id="dec_drop_py36", note="Must verify EOL status"
    )
    assert pin_res["status"] == "pinned"
    assert pin_res["decision_id"] == "dec_drop_py36"
