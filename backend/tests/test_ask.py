"""Ask feature: search ranking, tool schemas, and the agent's streaming contract."""

import asyncio
from unittest.mock import MagicMock

import pytest
from dig.agent import agent as agent_module
from dig.agent.agent import DecisionAgent
from dig.agent.tools import registry
from dig.graph.client import get_graph
from dig.graph.queries import search_decisions
from dig.graph.ranking import query_terms, score_decision, tokenize
from google.genai import types
from scripts.seed_demo_graph import seed_demo_graph


@pytest.fixture(scope="module")
def seeded_graph():
    graph_name = "dig_test_ask"
    graph = get_graph(graph_name)
    seed_demo_graph(graph=graph, graph_name=graph_name)
    return graph


def top(graph, query):
    return [d.id for d in search_decisions(graph, query=query).data]


# --- ranking -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected_first"),
    [
        ("Python 3.6", "dec_drop_py36"),
        ("Why was Python 3.6 dropped?", "dec_drop_py36"),
        ("python 3.7 support", "dec_drop_py36"),  # 3.7 only appears in the 3.6 decision summary
        ("python 2", "dec_drop_py2"),
        ("Why did Flask drop Python 2?", "dec_drop_py2"),
        ("async views", "dec_async_views"),
        ("who decided async", "dec_async_views"),
    ],
)
def test_search_puts_the_right_decision_first(seeded_graph, query, expected_first):
    assert top(seeded_graph, query)[0] == expected_first


def test_version_mismatch_is_not_a_strong_hit(seeded_graph):
    # Previously "python 2" ranked the 3.6 decision first because digits were discarded.
    ids = top(seeded_graph, "python 2")
    assert ids[0] == "dec_drop_py2"
    assert "dec_drop_py36" not in ids  # incidental match removed by the relative cutoff


def test_module_name_query_matches_by_module(seeded_graph):
    assert set(top(seeded_graph, "flask/views")) >= {"dec_async_views"}


def test_empty_query_returns_newest_first(seeded_graph):
    ids = top(seeded_graph, "")
    assert ids[0] == "dec_drop_py36"
    assert set(ids) == {"dec_drop_py36", "dec_async_views", "dec_drop_py2"}


def test_unrelated_query_returns_nothing(seeded_graph):
    assert top(seeded_graph, "kubernetes helm chart") == []


def test_filters_still_apply(seeded_graph):
    res = search_decisions(seeded_graph, query="python", status="superseded")
    assert [d.id for d in res.data] == ["dec_drop_py2"]


def test_tokenizer_keeps_versions_whole_and_stems():
    assert "3.6" in tokenize("Python 3.6 support")
    assert tokenize("dropped") == tokenize("dropping") == tokenize("drop")
    words, versions = query_terms("Why was Python 3.6 dropped?")
    assert versions == ["3.6"]
    assert "why" not in words and "python" in words


def test_score_is_zero_without_overlap():
    assert score_decision("kubernetes", "Drop Python 2 support", "", ["flask/compat"]) == 0.0


# --- tool schemas ----------------------------------------------------------------------------


def test_every_tool_param_has_a_real_description():
    for meta in registry.list_tools():
        for name, prop in meta.parameters_schema["properties"].items():
            assert not prop["description"].startswith("Parameter "), (meta.name, name)


def test_list_params_are_declared_as_arrays():
    paths = registry.get("check_proposal").parameters_schema["properties"]["paths"]
    assert paths == {
        "type": "array",
        "items": {"type": "string"},
        "description": paths["description"],
    }


def test_gemini_accepts_all_tool_declarations():
    agent = DecisionAgent(graph_name="dig_test_ask")
    declarations = agent._build_tools_declaration()[0].function_declarations
    assert len(declarations) == len(registry.list_tools())


# --- agent streaming contract ----------------------------------------------------------------


def response(part: types.Part):
    resp = MagicMock()
    resp.candidates = [types.Candidate(content=types.Content(role="model", parts=[part]))]
    return resp


def call(name, **args):
    part = types.Part()
    part.function_call = types.FunctionCall(name=name, args=args)
    return response(part)


def text(value):
    part = types.Part()
    part.text = value
    return response(part)


async def run(agent, question="Why was Python 3.6 dropped?"):
    return [ev async for ev in agent.ask_stream(question)]


@pytest.mark.asyncio
async def test_unverified_draft_is_never_streamed(seeded_graph):
    client = MagicMock()
    client.models.generate_content.side_effect = [
        call("trace_to_source", decision_id="dec_drop_py36"),
        text("Dropped in 2022 [[ev:made_up]]."),  # invented citation -> repair turn
        text("Dropped in PR #4400 [[ev:ev_drop_py36]]."),
    ]
    events = await run(DecisionAgent(graph_name="dig_test_ask", client=client, max_rounds=6))
    names = [e.event for e in events]
    assert "token" not in names  # raw drafts with [[ev:...]] markers must not reach the UI
    answer = next(e for e in events if e.event == "answer").data
    assert "[[ev:" not in answer["markdown"]
    assert answer["verification"] == {"valid": 1, "invalid": 0, "repaired": True}


@pytest.mark.asyncio
async def test_status_events_bracket_the_work(seeded_graph):
    client = MagicMock()
    client.models.generate_content.side_effect = [
        call("trace_to_source", decision_id="dec_drop_py36"),
        text("Dropped in PR #4400 [[ev:ev_drop_py36]]."),
    ]
    events = await run(DecisionAgent(graph_name="dig_test_ask", client=client))
    phases = [e.data["phase"] for e in events if e.event == "status"]
    assert phases == ["thinking", "thinking", "verifying"]
    assert [e.event for e in events][-2:] == ["answer", "done"]


@pytest.mark.asyncio
async def test_model_that_skips_tools_is_pushed_back_once(seeded_graph):
    client = MagicMock()
    client.models.generate_content.side_effect = [
        text("Flask dropped 3.6 because it felt like it."),  # no tools used
        call("trace_to_source", decision_id="dec_drop_py36"),
        text("Dropped in PR #4400 [[ev:ev_drop_py36]]."),
    ]
    events = await run(DecisionAgent(graph_name="dig_test_ask", client=client))
    answer = next(e for e in events if e.event == "answer").data
    assert answer["citations"][0]["evidence_id"] == "ev_drop_py36"
    assert client.models.generate_content.call_count == 3


@pytest.mark.asyncio
async def test_llm_timeout_is_reported_not_hung(seeded_graph, monkeypatch):
    monkeypatch.setattr(agent_module, "LLM_TIMEOUT_S", 0.05)
    import time

    client = MagicMock()
    client.models.generate_content.side_effect = lambda **_: time.sleep(0.5)
    events = await asyncio.wait_for(
        run(DecisionAgent(graph_name="dig_test_ask", client=client)), timeout=5
    )
    error = next(e for e in events if e.event == "error")
    assert "did not answer" in error.data["message"]
    assert events[-1].event == "done"


@pytest.mark.asyncio
async def test_offline_simulator_cites_the_decision_it_names(seeded_graph, monkeypatch):
    """Regression: 'Why was Python 3.6 dropped?' used to cite the Python 2 quote."""
    from dig.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(settings, "dig_offline", True)
    events = await run(DecisionAgent(graph_name="dig_test_ask"))
    answer = next(e for e in events if e.event == "answer").data
    assert "dec_drop_py36" in answer["markdown"]
    assert [c["decision_id"] for c in answer["citations"]] == ["dec_drop_py36"]
    assert "3.6" in answer["citations"][0]["quote"]
