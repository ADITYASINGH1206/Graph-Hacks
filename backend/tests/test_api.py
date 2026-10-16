"""Tests for FastAPI backend endpoints and SSE streaming."""

from unittest.mock import patch

import pytest
from dig.agent.agent import AgentEvent
from dig.api.main import app
from dig.graph.client import get_graph
from fastapi.testclient import TestClient
from scripts.seed_demo_graph import seed_demo_graph

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_graph():
    """Seed the default graph so endpoints have test data."""
    graph = get_graph()
    seed_demo_graph(graph=graph)


def test_openapi_schema_matches_contract():
    """Verify that all required endpoints in docs/API_CONTRACT.md exist in the OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]

    expected_paths = [
        "/health",
        "/ask",
        "/guard",
        "/decisions",
        "/decisions/{decision_id}",
        "/subgraph",
        "/sync",
        "/people/{login}",
    ]
    for p in expected_paths:
        assert p in paths, f"Path {p} missing from API schema"


def test_health_endpoint():
    """Test GET /health returns expected status and count keys."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "graph" in data
    assert "counts" in data
    assert "Decision" in data["counts"]
    assert "Evidence" in data["counts"]
    assert "Person" in data["counts"]


def test_list_decisions_endpoint():
    """Test GET /decisions with and without filters."""
    res = client.get("/decisions")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) >= 1

    # Filter by query
    res_filtered = client.get("/decisions?q=Python")
    assert res_filtered.status_code == 200
    items = res_filtered.json()["items"]
    assert len(items) >= 1
    assert any("Python" in item["title"] for item in items)


def test_get_decision_detail():
    """Test GET /decisions/{id} returns decision, citations, and lineage."""
    res = client.get("/decisions/dec_drop_py36")
    assert res.status_code == 200
    data = res.json()
    assert data["decision"]["id"] == "dec_drop_py36"
    assert "evidence" in data
    assert len(data["evidence"]) >= 1
    assert data["evidence"][0]["quote"] != ""
    assert "people" in data
    assert "lineage" in data
    assert "impact" in data


def test_get_subgraph():
    """Test GET /subgraph returns nodes and edges around center."""
    res = client.get("/subgraph?center=Decision:dec_drop_py36&depth=1")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) >= 1


def test_get_person_detail():
    """Test GET /people/{login} for davidism."""
    res = client.get("/people/davidism")
    assert res.status_code == 200
    data = res.json()
    assert data["login"] == "davidism"
    assert "modules" in data
    assert "decisions" in data


def test_guard_baseline():
    """Test POST /guard accepts description and paths."""
    res = client.post(
        "/guard",
        json={"description": "Drop Python 3.8", "paths": ["src/flask/compat.py"]},
    )
    assert res.status_code == 200
    data = res.json()
    assert "conflicts" in data
    assert "alignments" in data
    assert "reversed_before" in data


def test_ask_sse_stream_events():
    """Test POST /ask SSE streaming event sequence."""

    async def mock_events(*args, **kwargs):
        yield AgentEvent(
            event="tool_call",
            data={"id": "call_1", "name": "search_decisions", "input": {"query": "test"}},
        )
        yield AgentEvent(
            event="tool_result",
            data={
                "id": "call_1",
                "name": "search_decisions",
                "summary": "Found 1",
                "graph_elements": {"nodes": [], "edges": []},
            },
        )
        yield AgentEvent(event="token", data={"text": "Here is the answer"})
        yield AgentEvent(
            event="answer",
            data={
                "markdown": "Answer text [1]",
                "citations": [
                    {
                        "n": 1,
                        "evidence_id": "ev_1",
                        "quote": "Quote",
                        "url": "https://github.com/pallets/flask/pull/1",
                        "author": "davidism",
                        "ts": "2022-01-01",
                        "decision_id": "dec_1",
                    }
                ],
                "path": {"nodes": [], "edges": []},
                "verification": {"valid": 1, "invalid": 0, "repaired": False},
            },
        )
        yield AgentEvent(event="done", data={"session_id": "sess_123", "tool_rounds": 1})

    with patch("dig.agent.agent.DecisionAgent.ask_stream", side_effect=mock_events):
        res = client.post(
            "/ask",
            json={"question": "Why was Python 3.6 dropped?"},
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        body = res.text

        # Verify event stream sequence
        events_in_body = [line for line in body.split("\n") if line.startswith("event: ")]
        assert events_in_body == [
            "event: tool_call",
            "event: tool_result",
            "event: token",
            "event: answer",
            "event: done",
        ]

        # Verify citation URLs are non-empty
        assert "https://github.com/pallets/flask/pull/1" in body
