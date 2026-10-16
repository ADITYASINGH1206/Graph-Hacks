"""Tests covering core queries against the seeded demo graph."""

import pytest
from dig.graph.client import get_graph
from dig.graph.queries import (
    active_decisions_for_modules,
    get_decision,
    get_lineage,
    impact_of,
    search_decisions,
    shortest_path,
    who_knows,
)
from scripts.seed_demo_graph import seed_demo_graph


@pytest.fixture(scope="module")
def seeded_graph():
    """Ensure the test graph is seeded with demo data."""
    graph_name = "dig_test_queries"
    graph = get_graph(graph_name)
    seed_demo_graph(graph=graph, graph_name=graph_name)
    return graph


def test_search_decisions_fulltext(seeded_graph):
    """Test fulltext search for decisions."""
    res = search_decisions(seeded_graph, query="Python")
    assert len(res.data) >= 1
    ids = [d.id for d in res.data]
    assert "dec_drop_py36" in ids or "dec_drop_py2" in ids
    assert len(res.graph_elements.nodes) >= 1


def test_search_decisions_filter(seeded_graph):
    """Test decision search with module and status filtering."""
    res = search_decisions(
        seeded_graph,
        query="",
        module="flask/compat",
        status="active",
    )
    assert len(res.data) == 1
    assert res.data[0].id == "dec_drop_py36"
    assert res.data[0].status == "active"


def test_get_decision_detail(seeded_graph):
    """Test retrieving complete decision with evidence, people, sources."""
    res = get_decision(seeded_graph, "dec_drop_py36")
    assert res.data is not None
    assert res.data.id == "dec_drop_py36"
    assert len(res.data.evidence) >= 1
    assert "EOL" in res.data.evidence[0].quote
    assert len(res.data.people) >= 1
    assert res.data.people[0].login == "davidism"
    assert len(res.graph_elements.nodes) >= 3


def test_get_decision_not_found(seeded_graph):
    """Test get_decision for non-existent decision returns None."""
    res = get_decision(seeded_graph, "non_existent_id")
    assert res.data is None


def test_get_lineage(seeded_graph):
    """Test decision lineage for superseding relations."""
    res = get_lineage(seeded_graph, "dec_drop_py36")
    assert len(res.data.hops) >= 1
    assert res.data.hops[0].relation == "SUPERSEDES"
    assert res.data.hops[0].target_id == "dec_drop_py2"
    # Chronological sort check
    dec_ids = [d.id for d in res.data.decisions]
    assert dec_ids == ["dec_drop_py2", "dec_drop_py36"]


def test_who_knows(seeded_graph):
    """Test expertise scoring query on a module."""
    res = who_knows(seeded_graph, "flask/app", limit=5)
    assert len(res.data) >= 2
    # David Lord has higher score than Armin
    assert res.data[0].login == "davidism"
    assert res.data[0].score >= res.data[1].score
    assert all(item.login != "pallets-bot" for item in res.data)  # Bots excluded


def test_impact_of(seeded_graph):
    """Test impact analysis for a decision."""
    res = impact_of(seeded_graph, "dec_drop_py36")
    assert res.data.decision_id == "dec_drop_py36"
    affected_names = [a.get("name") for a in res.data.affected]
    assert "flask/compat" in affected_names or "flask/app" in affected_names
    assert "2.2.0" in res.data.releases


def test_active_decisions_for_modules(seeded_graph):
    """Test guard query for active decisions affecting given modules."""
    res = active_decisions_for_modules(seeded_graph, ["flask/views"])
    assert len(res.data) == 1
    assert res.data[0].id == "dec_async_views"
    assert res.data[0].type == "adoption"


def test_shortest_path(seeded_graph):
    """Test path discovery between two nodes."""
    res = shortest_path(seeded_graph, "davidism", "flask/views")
    assert res.data is not None
    assert res.data.length >= 1
    assert len(res.data.path_nodes) >= 2
    assert len(res.graph_elements.nodes) >= 2
