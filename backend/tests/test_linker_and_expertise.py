"""Unit tests for decision linking and expertise scoring."""

from dig.extract.expertise import compute_and_write_expertise, parse_timestamp
from dig.extract.linker import (
    detect_explicit_revert,
    find_candidate_pairs,
)
from dig.graph.client import get_graph
from scripts.seed_demo_graph import seed_demo_graph


def test_detect_explicit_revert():
    """Verify explicit revert detection from PR titles and summaries."""
    newer = {
        "title": "Revert PR #3500",
        "summary": "This reverts commit abc1234 and restores Python 2 compat code.",
    }
    older = {
        "source_number": 3500,
        "type": "deprecation",
    }
    revert_info = detect_explicit_revert(newer, older)
    assert revert_info is not None
    assert revert_info["relation"] == "reverses"
    assert revert_info["confidence"] == 1.0


def test_detect_explicit_revert_non_revert():
    """Verify non-revert decision pair returns None."""
    newer = {"title": "Add async route handlers", "summary": "Adopted asgiref."}
    older = {"source_number": 3500, "type": "deprecation"}
    assert detect_explicit_revert(newer, older) is None


def test_find_candidate_pairs():
    """Verify candidate pair generation for decisions sharing modules."""
    test_graph = get_graph("dig_test_linker")
    seed_demo_graph(graph=test_graph, graph_name="dig_test_linker")

    candidates = find_candidate_pairs(test_graph, max_pairs=10)
    assert len(candidates) >= 1
    # Check that older and newer are ordered chronologically
    for pair in candidates:
        older = pair["older"]
        newer = pair["newer"]
        assert (older.get("decided_at") or "") <= (newer.get("decided_at") or "")


def test_parse_timestamp():
    """Verify ISO timestamp parsing with UTC timezone."""
    dt = parse_timestamp("2022-03-20T16:00:00Z")
    assert dt.year == 2022
    assert dt.month == 3
    assert dt.tzinfo is not None


def test_expertise_scoring_and_bot_exclusion():
    """Verify KNOWS edges are computed and bots are excluded from expertise."""
    test_graph = get_graph("dig_test_expertise")
    seed_demo_graph(graph=test_graph, graph_name="dig_test_expertise")

    res = compute_and_write_expertise(graph=test_graph)
    assert res["knows_edges"] >= 1

    # Check bots are excluded
    check_bot = test_graph.query(
        "MATCH (p:Person {login: 'pallets-bot'})-[:KNOWS]->() RETURN count(p)"
    )
    assert check_bot.result_set[0][0] == 0

    # Check davidism has KNOWS edges
    check_david = test_graph.query(
        "MATCH (p:Person {login: 'davidism'})-[k:KNOWS]->(m:Module) RETURN count(m)"
    )
    assert check_david.result_set[0][0] >= 1
