"""Tests for agent loop, citation verifier, and repair turns."""

from unittest.mock import MagicMock

import pytest
from dig.agent.agent import DecisionAgent
from dig.agent.verifier import (
    check_citations,
    extract_markers,
    extract_sentences,
    finalize_answer,
)
from dig.graph.client import get_graph
from google.genai import types
from scripts.seed_demo_graph import seed_demo_graph


@pytest.fixture(scope="module")
def seeded_graph():
    """Ensure a seeded test graph exists."""
    graph_name = "dig_test_agent"
    graph = get_graph(graph_name)
    seed_demo_graph(graph=graph, graph_name=graph_name)
    return graph


def test_extract_markers_and_sentences():
    """Verify regex extraction of evidence markers and sentence boundary splitting."""
    text = (
        "Flask deprecated Python 2.7 in 2018 [[ev:ev_drop_py2]]. "
        "Later in 2020, Python 3.6 was removed [[ev:ev_drop_py36_pr]]. "
        "A regular uncited sentence follows."
    )
    markers = extract_markers(text)
    assert markers == ["ev_drop_py2", "ev_drop_py36_pr"]

    sentences = extract_sentences(text)
    assert len(sentences) == 3


def test_verifier_valid_citations():
    """Test verification when all citations match known evidence IDs."""
    text = "Python 2 was removed in 1.0 [[ev:ev_1]]."
    known_ids = {"ev_1"}

    check = check_citations(text, known_ids)
    assert check.is_valid is True
    assert check.repair_prompt is None

    evidence_map = {
        "ev_1": {
            "evidence_id": "ev_1",
            "quote": "Drop support for Python 2.6 and 3.3",
            "url": "https://github.com/pallets/flask/pull/123",
            "author": "davidism",
            "ts": "2018-04-01T12:00:00Z",
            "decision_id": "dec_1",
        }
    }
    final_md, citations, verification = finalize_answer(text, evidence_map)
    assert "[1]" in final_md
    assert "[[ev:ev_1]]" not in final_md
    assert len(citations) == 1
    assert citations[0].evidence_id == "ev_1"
    assert citations[0].quote == "Drop support for Python 2.6 and 3.3"
    assert verification.valid == 1
    assert verification.invalid == 0
    assert verification.repaired is False


def test_verifier_catches_unrecognized_id_and_triggers_repair():
    """Test detection of hallucinated/unrecognized evidence ID."""
    text = "We decided to deprecate XML in 2021 [[ev:hallucinated_id_999]]."
    known_ids = {"ev_legit"}

    check = check_citations(text, known_ids)
    assert check.is_valid is False
    assert "hallucinated_id_999" in check.invalid_ids
    assert check.repair_prompt is not None
    assert "These claims lack valid evidence" in check.repair_prompt
    assert "hallucinated_id_999" in check.repair_prompt


def test_verifier_strips_lingering_invalid_markers():
    """If an invalid marker persists after repair, it is stripped and marked unverified."""
    text = "A claim with bad marker [[ev:fake_123]]."
    evidence_map = {}  # empty

    final_md, citations, verification = finalize_answer(text, evidence_map, was_repaired=True)
    assert "[[ev:fake_123]]" not in final_md
    assert "(Not verified against the graph)" in final_md
    assert len(citations) == 0
    assert verification.invalid == 1
    assert verification.repaired is True


@pytest.mark.asyncio
async def test_agent_tool_loop_and_repair_turn(seeded_graph):
    """Test full agent loop with mocked Gemini responses:

    - Round 1: Model calls search_decisions
    - Round 2: Model returns answer with an invented marker [[ev:fake_404]]
    - Verifier triggers repair prompt
    - Round 3: Model returns repaired answer citing [[ev:ev_drop_py36_pr]]
    - Agent finalizes with verification.repaired = True
    """
    mock_client = MagicMock()

    # Create mock response 1: Function call to trace_to_source
    resp1 = MagicMock()
    fc_part = types.Part()
    fc_part.function_call = types.FunctionCall(
        name="trace_to_source",
        args={"decision_id": "dec_drop_py36"},
    )
    resp1.candidates = [types.Candidate(content=types.Content(parts=[fc_part]))]

    # Create mock response 2: Text answer with bad marker
    resp2 = MagicMock()
    text_part_bad = types.Part()
    text_part_bad.text = "Flask dropped Python 3.6 support in version 2.0 [[ev:fake_404]]."
    resp2.candidates = [types.Candidate(content=types.Content(parts=[text_part_bad]))]

    # Create mock response 3: Repaired text answer citing real evidence from tool
    resp3 = MagicMock()
    text_part_repaired = types.Part()
    text_part_repaired.text = "Flask dropped Python 3.6 support in PR #4400 [[ev:ev_drop_py36]]."
    resp3.candidates = [types.Candidate(content=types.Content(parts=[text_part_repaired]))]

    mock_client.models.generate_content.side_effect = [resp1, resp2, resp3]

    agent = DecisionAgent(
        graph_name="dig_test_agent",
        client=mock_client,
        max_rounds=5,
    )

    events = []
    async for ev in agent.ask_stream("Why was Python 3.6 dropped?"):
        events.append(ev)

    event_types = [e.event for e in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "answer" in event_types
    assert "done" in event_types

    # Find answer event
    answer_event = next(e for e in events if e.event == "answer")
    answer_data = answer_event.data

    assert "[1]" in answer_data["markdown"]
    assert "[[ev:" not in answer_data["markdown"]
    assert len(answer_data["citations"]) >= 1
    assert answer_data["citations"][0]["evidence_id"] == "ev_drop_py36"
    assert answer_data["verification"]["repaired"] is True
    assert answer_data["verification"]["valid"] == 1
    assert answer_data["verification"]["invalid"] == 0
