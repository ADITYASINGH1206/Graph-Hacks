"""Tests for offline-mode opt-in, memory graph isolation, API input limits and CORS."""

import pytest
from dig.agent.agent import DecisionAgent
from dig.api.main import app
from dig.config import settings
from dig.graph.client import get_graph
from fastapi.testclient import TestClient
from scripts.seed_demo_graph import seed_demo_graph

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def seeded_graph():
    seed_demo_graph(graph=get_graph())


@pytest.fixture
def no_api_key(monkeypatch):
    """Clear every way a Gemini key can be provided."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(settings, "gemini_api_key", "")


# --- memory graph isolation -------------------------------------------------


def test_memory_graph_names_do_not_collide():
    ids = ["a-b", "a_b", "a.b", "A.B", "a b", "a/b", "alice@x.com", "alice_x_com"]
    names = {settings.memory_graph_name(u) for u in ids}
    assert len(names) == len(ids), "distinct user ids must map to distinct memory graphs"


def test_memory_graph_name_is_stable_and_safe():
    name = settings.memory_graph_name("Réne O'Brien; DROP GRAPH x")
    assert name == settings.memory_graph_name("Réne O'Brien; DROP GRAPH x")
    assert name.startswith("mem_")
    assert name.isascii()
    assert all(c.isalnum() or c == "_" for c in name)
    assert len(name) <= 4 + 32 + 1 + 10


def test_memory_graph_name_blank_user_falls_back():
    assert settings.memory_graph_name("   ") == settings.memory_graph_name("anonymous")


# --- no silent fake answers ---------------------------------------------------


async def test_missing_key_is_an_error_not_a_canned_answer(no_api_key, monkeypatch):
    monkeypatch.setattr(settings, "dig_offline", False)
    events = [e async for e in DecisionAgent().ask_stream("Why was Python 3.6 dropped?")]
    names = [e.event for e in events if e.event != "recall"]
    assert names == ["error", "done"]
    assert "GEMINI_API_KEY" in events[-2].data["message"]
    assert "DIG_OFFLINE" in events[-2].data["message"]


async def test_offline_mode_requires_explicit_opt_in(no_api_key, monkeypatch):
    monkeypatch.setattr(settings, "dig_offline", True)
    events = [e async for e in DecisionAgent().ask_stream("Why was Python 3.6 dropped?")]
    names = [e.event for e in events]
    assert "answer" in names
    done = events[-1]
    assert done.event == "done"
    assert done.data["offline"] is True


# --- /health llm_mode -----------------------------------------------------------


def test_health_reports_llm_mode(no_api_key, monkeypatch):
    monkeypatch.setattr(settings, "dig_offline", False)
    assert client.get("/health").json()["llm_mode"] == "no_key"

    monkeypatch.setattr(settings, "dig_offline", True)
    assert client.get("/health").json()["llm_mode"] == "offline"

    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    assert client.get("/health").json()["llm_mode"] == "live"


# --- request validation ---------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 2001},
        {"question": "ok", "user_id": ""},
        {"question": "ok", "user_id": "has space"},
        {"question": "ok", "user_id": "../etc/passwd"},
        {"question": "ok", "user_id": "u" * 65},
    ],
)
def test_ask_rejects_invalid_input(payload):
    assert client.post("/ask", json=payload).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"description": ""},
        {"description": "x" * 4001},
        {"description": "ok", "paths": ["p"] * 51},
        {"description": "ok", "paths": ["x" * 301]},
    ],
)
def test_guard_rejects_invalid_input(payload):
    assert client.post("/guard", json=payload).status_code == 422


def test_guard_accepts_valid_input():
    res = client.post(
        "/guard",
        json={"description": "Restore Python 3.6 helpers", "paths": ["src/flask/compat.py"]},
    )
    assert res.status_code == 200


# --- CORS -------------------------------------------------------------------------


def _preflight(origin: str):
    return client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_cors_allows_the_dev_frontend_only():
    ok = _preflight("http://localhost:5173")
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"

    evil = _preflight("https://evil.example")
    assert "access-control-allow-origin" not in evil.headers


def test_cors_never_allows_credentials():
    res = _preflight("http://localhost:5173")
    assert "access-control-allow-credentials" not in res.headers
