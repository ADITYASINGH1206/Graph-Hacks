"""Tests for agent tools and MCP tool registry."""

import pytest
from dig.agent.tools import registry
from dig.graph.client import get_graph
from scripts.seed_demo_graph import seed_demo_graph


@pytest.fixture(scope="module")
def seeded_graph():
    """Ensure a dedicated test graph is seeded with demo data."""
    graph_name = "dig_test_tools"
    graph = get_graph(graph_name)
    seed_demo_graph(graph=graph, graph_name=graph_name)
    return graph


def test_registry_contains_all_tools():
    """Verify that all 10 required tools are registered with schemas."""
    expected = {
        "search_decisions",
        "get_decision",
        "trace_to_source",
        "decision_lineage",
        "who_knows",
        "who_decided",
        "impact_of",
        "find_path",
        "central_people",
        "recent_changes",
    }
    registered = set(registry.tools.keys())
    assert expected.issubset(registered), f"Missing tools: {expected - registered}"

    for name in expected:
        meta = registry.get(name)
        assert meta is not None
        assert meta.description != ""
        assert "type" in meta.parameters_schema
        assert meta.parameters_schema["type"] == "object"


def test_tool_envelopes_and_calls(seeded_graph):
    """Test calling each tool and verifying the 3-part envelope: data, graph_elements, summary."""
    tools_to_test = [
        ("search_decisions", {"query": "Python"}),
        ("get_decision", {"decision_id": "dec_drop_py36"}),
        ("trace_to_source", {"decision_id": "dec_drop_py36"}),
        ("decision_lineage", {"decision_id": "dec_drop_py36"}),
        ("who_knows", {"module": "flask/compat", "limit": 5}),
        ("who_decided", {"decision_id": "dec_drop_py36"}),
        ("impact_of", {"decision_id": "dec_drop_py2"}),
        ("find_path", {"a_id": "dec_drop_py36", "b_id": "dec_drop_py2"}),
        ("central_people", {"scope": "all", "limit": 3}),
        ("recent_changes", {"since": "2010-01-01", "limit": 5}),
    ]

    for tool_name, kwargs in tools_to_test:
        meta = registry.get(tool_name)
        assert meta is not None
        # Call tool with graph passed
        res = meta.func(graph=seeded_graph, **kwargs)
        assert isinstance(res, dict), f"Tool {tool_name} did not return dict"
        assert "data" in res, f"Tool {tool_name} missing 'data'"
        assert "graph_elements" in res, f"Tool {tool_name} missing 'graph_elements'"
        assert "summary" in res, f"Tool {tool_name} missing 'summary'"
        assert isinstance(res["summary"], str)
        assert len(res["summary"]) > 0


def test_central_people_pagerank(seeded_graph):
    """Test central_people PageRank output on seeded graph."""
    meta = registry.get("central_people")
    res = meta.func(graph=seeded_graph, scope="all", limit=5)
    data = res["data"]
    assert isinstance(data, list)
    assert len(data) >= 1
    # Check ranking structure
    first = data[0]
    assert "login" in first
    assert "score" in first
    assert "rank" in first
    assert first["rank"] == 1
