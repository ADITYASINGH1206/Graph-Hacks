"""Tests for Time Machine, knowledge-risk scoring, PR Guard and the LLM guard judge."""

import datetime as dt
import json
from types import SimpleNamespace

import httpx
import pytest
from dig.agent import guard
from dig.api import pr_guard
from dig.api.main import app
from dig.config import settings
from dig.graph.client import get_graph
from dig.graph.insights import (
    DecisionRecord,
    ExpertRow,
    Relation,
    compute_module_risk,
    compute_range,
    compute_risk_report,
    compute_snapshot,
    parse_ts,
)
from dig.graph.models import GraphNode
from fastapi.testclient import TestClient
from scripts.seed_demo_graph import seed_demo_graph

client = TestClient(app)
UTC = dt.UTC


def D(s: str) -> dt.datetime:
    parsed = parse_ts(s)
    assert parsed is not None
    return parsed


def rec(
    id_: str, start: str | None, end: str | None = None, status: str = "active", modules=()
) -> DecisionRecord:
    node = GraphNode(
        id=f"Decision:{id_}", label="Decision", title=id_, props={"id": id_, "status": status}
    )
    mods = [GraphNode(id=f"Module:{m}", label="Module", title=m, props={}) for m in modules]
    return DecisionRecord(
        id=id_,
        node=node,
        modules=mods,
        start=D(start) if start else None,
        end=D(end) if end else None,
    )


# ------------------------------------------------------------------ parse_ts


@pytest.mark.parametrize(
    "value",
    [
        "2022-03-20",
        "2022-03-20T16:00:00Z",
        "2022-03-20T16:00:00+00:00",
        "2022-03-20T21:30:00+05:30",
    ],
)
def test_parse_ts_accepts_iso_forms_as_utc(value):
    parsed = parse_ts(value)
    assert (
        parsed is not None and parsed.tzinfo is not None and parsed.utcoffset() == dt.timedelta(0)
    )


@pytest.mark.parametrize("value", [None, "", "yesterday", "2022-13-45", "20/03/2022"])
def test_parse_ts_rejects_garbage(value):
    assert parse_ts(value) is None


# ------------------------------------------------------------------ time machine (pure)


def test_snapshot_splits_active_ended_upcoming_undated():
    records = [
        rec("old", "2020-01-01", "2021-01-01", status="superseded", modules=["m/a"]),
        rec("current", "2020-06-01", modules=["m/a", "m/b"]),
        rec("future", "2023-01-01"),
        rec("nodate", None),
    ]
    snap = compute_snapshot(records, [], D("2022-01-01"))
    assert [d.id for d in snap.active] == ["current"]
    assert [d.id for d in snap.ended] == ["old"]
    assert snap.ended[0].status == "superseded"
    assert snap.upcoming_count == 1
    assert snap.undated_count == 1


def test_snapshot_boundary_is_end_exclusive_and_start_inclusive():
    records = [rec("x", "2020-01-01", "2021-01-01", status="reversed")]
    assert [d.id for d in compute_snapshot(records, [], D("2020-01-01")).active] == ["x"]
    at_end = compute_snapshot(records, [], D("2021-01-01"))
    assert at_end.active == [] and at_end.ended[0].status == "reversed"


def test_snapshot_graph_has_status_as_of_and_relation_edges_only_when_both_visible():
    records = [
        rec("older", "2020-01-01", "2022-01-01", status="superseded", modules=["m/a"]),
        rec("newer", "2022-01-01", modules=["m/a"]),
    ]
    rels = [Relation(source="newer", target="older", type="SUPERSEDES", reason="replaced")]

    after = compute_snapshot(records, rels, D("2022-06-01"))
    statuses = {n.id: n.props["status"] for n in after.graph.nodes if n.label == "Decision"}
    assert statuses == {"Decision:older": "superseded", "Decision:newer": "active"}
    assert any(e.type == "SUPERSEDES" for e in after.graph.edges)
    assert len({n.id for n in after.graph.nodes}) == len(after.graph.nodes)  # no duplicate nodes

    before = compute_snapshot(records, rels, D("2021-01-01"))
    assert {n.props["status"] for n in before.graph.nodes if n.label == "Decision"} == {"active"}
    assert not any(e.type == "SUPERSEDES" for e in before.graph.edges)


def test_range_orders_events_and_counts_undated():
    records = [rec("b", "2021-01-01", "2022-01-01"), rec("a", "2020-01-01"), rec("n", None)]
    rng = compute_range(records)
    assert rng.min_date.startswith("2020-01-01") and rng.max_date.startswith("2022-01-01")
    assert [e.kind for e in rng.events] == ["decided", "decided", "ended"]
    assert rng.undated_count == 1


def test_range_empty():
    rng = compute_range([])
    assert rng.min_date is None and rng.max_date is None and rng.events == []


# ------------------------------------------------------------------ knowledge risk (pure)

AS_OF = D("2024-01-01")


def rows(module, *people):
    return [
        ExpertRow(module=module, login=name, score=score, last_active=last)
        for name, score, last in people
    ]


def risk_of(module_rows, statuses=None):
    report = compute_module_risk(module_rows, statuses or {}, AS_OF)
    return {m.module: m for m in report}


def test_risk_levels():
    data = (
        rows("none_active", ("a", 5, "2020-01-01"), ("b", 4, "2021-01-01"))
        + rows("sole", ("a", 9, "2023-12-01"), ("b", 1, "2020-01-01"))
        + rows(
            "concentrated", ("a", 9, "2023-12-01"), ("b", 1, "2023-11-01"), ("c", 1, "2023-10-01")
        )
        + rows("pair", ("a", 5, "2023-12-01"), ("b", 5, "2023-11-01"))
        + rows("healthy", ("a", 3, "2023-12-01"), ("b", 3, "2023-11-01"), ("c", 3, "2023-10-01"))
    )
    got = risk_of(data, {"orphan": ["active"]})
    assert got["none_active"].risk == "critical"
    assert got["sole"].risk == "high" and "Only one active expert: a" in got["sole"].reasons[0]
    assert got["concentrated"].risk == "medium" and got["concentrated"].bus_factor == 1
    assert got["pair"].risk == "medium" and got["pair"].active_experts == 2
    assert got["healthy"].risk == "low" and got["healthy"].bus_factor == 2
    assert got["orphan"].risk == "critical"  # has decisions but no known expert
    assert got["orphan"].reasons == ["No known expert in the graph"]


def test_risk_sorted_most_severe_first_and_impact_raises_score():
    data = rows("a", ("x", 1, "2023-12-01")) + rows("b", ("y", 1, "2023-12-01"))
    report = compute_module_risk(data, {"a": ["active"] * 5, "b": []}, AS_OF)
    assert [m.module for m in report] == ["a", "b"]  # same level, more decisions ranks first
    assert report[0].risk_score > report[1].risk_score
    assert all(0 <= m.risk_score <= 100 for m in report)


def test_risk_activity_window_is_respected():
    data = rows("m", ("a", 5, "2023-01-02"), ("b", 5, "2022-12-30"))
    one_year = compute_module_risk(data, {}, AS_OF, window_days=365)[0]
    assert one_year.active_experts == 1
    two_years = compute_module_risk(data, {}, AS_OF, window_days=730)[0]
    assert two_years.active_experts == 2


def test_risk_report_reference_date_sources():
    data = rows("m", ("a", 5, "2023-05-05"))
    assert compute_risk_report(data, {}).as_of_source == "graph_latest"
    assert compute_risk_report(data, {}).as_of.startswith("2023-05-05")
    assert (
        compute_risk_report(data, {}, requested_as_of=D("2025-01-01")).as_of_source == "requested"
    )
    empty = compute_risk_report([], {}, now=D("2026-01-01"))
    assert empty.as_of_source == "now" and empty.modules == []


# ------------------------------------------------------------------ endpoints (seed graph)


@pytest.fixture(scope="module", autouse=True)
def seeded_graph():
    seed_demo_graph(graph=get_graph())


def test_timeline_range_endpoint():
    body = client.get("/timeline/range").json()
    assert body["min_date"].startswith("2020-05-15")
    assert body["max_date"].startswith("2022-03-20")
    assert {e["decision_id"] for e in body["events"]} >= {"dec_drop_py2", "dec_async_views"}


def test_timeline_snapshot_endpoint_tells_the_story():
    mid = client.get("/timeline/snapshot", params={"date": "2021-06-01"}).json()
    assert {d["id"] for d in mid["active"]} == {"dec_drop_py2", "dec_async_views"}
    assert mid["upcoming_count"] == 1

    late = client.get("/timeline/snapshot", params={"date": "2023-01-01"}).json()
    assert {d["id"] for d in late["active"]} == {"dec_drop_py36", "dec_async_views"}
    assert [d["id"] for d in late["ended"]] == ["dec_drop_py2"]
    assert any(e["type"] == "SUPERSEDES" for e in late["graph"]["edges"])


@pytest.mark.parametrize("bad", ["", "soon", "2021-99-99"])
def test_timeline_snapshot_rejects_bad_dates(bad):
    assert client.get("/timeline/snapshot", params={"date": bad}).status_code == 422


def test_risk_endpoint():
    body = client.get("/risk/modules").json()
    assert body["as_of_source"] == "graph_latest"
    names = {m["module"] for m in body["modules"]}
    assert {"flask/app", "flask/compat", "flask/views"} <= names
    assert all(m["risk"] in ("critical", "high", "medium", "low") for m in body["modules"])
    assert client.get("/risk/modules", params={"as_of": "not-a-date"}).status_code == 422
    assert client.get("/risk/modules", params={"window_days": 1}).status_code == 422


# ------------------------------------------------------------------ PR Guard


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/pallets/flask/pull/5000", ("pallets", "flask", 5000)),
        ("https://github.com/pallets/flask/pull/5000/files", ("pallets", "flask", 5000)),
        ("  https://github.com/a-b/c.d_e/pull/1?diff=split#x ", ("a-b", "c.d_e", 1)),
    ],
)
def test_parse_pr_url_accepts_pull_links(url, expected):
    assert pr_guard.parse_pr_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/pallets/flask/pull/1",
        "https://github.com.evil.example/pallets/flask/pull/1",
        "https://github.com@evil.example/pallets/flask/pull/1",
        "https://evil.example/https://github.com/pallets/flask/pull/1",
        "https://github.com/pallets/flask/issues/1",
        "https://github.com/pallets/flask/pull/abc",
        "https://github.com/pallets/flask/pull/1/../../x",
        "https://github.com/pallets/flask",
        "file:///etc/passwd",
        "",
    ],
)
def test_parse_pr_url_rejects_everything_else(url):
    with pytest.raises(ValueError):
        pr_guard.parse_pr_url(url)


def _fake_pr(**over):
    base = dict(
        owner="pallets",
        repo="flask",
        number=7,
        title="Restore Python 3.6 compatibility helpers",
        body="Re-add support for Python 3.6 in compat.",
        state="open",
        author="newbie",
        url="https://github.com/pallets/flask/pull/7",
        additions=10,
        deletions=2,
        changed_files=1,
        files=["src/flask/compat.py"],
        truncated_files=False,
    )
    base.update(over)
    return pr_guard.PullRequestData(**base)


def test_pr_guard_endpoint_flags_conflict_and_suggests_deciders(monkeypatch):
    monkeypatch.setattr(pr_guard, "fetch_pr", lambda o, r, n: _fake_pr())
    monkeypatch.setattr(guard, "_judge_client", lambda: None)  # heuristic path
    res = client.post("/guard/pr", json={"url": "https://github.com/pallets/flask/pull/7"})
    assert res.status_code == 200
    body = res.json()
    assert body["pr"]["number"] == 7 and body["pr"]["files_checked"] == 1
    assert body["repo_matches_graph"] is True
    assert body["guard"]["judge"] == "heuristic"
    assert body["guard"]["conflicts"], "restoring Python 3.6 helpers must conflict"
    assert body["suggested_reviewers"], "deciders of the conflicting decision are suggested"
    assert "newbie" not in body["suggested_reviewers"]


def test_pr_guard_never_invents_reviewers():
    result = guard.run_decision_guard("Restore Python 3.6 compat", ["src/flask/compat.py"])
    for conflict in result["conflicts"]:
        assert all(isinstance(p, str) and p for p in conflict["people"])
    source = open(guard.__file__, encoding="utf-8").read()
    assert 'or ["davidism"]' not in source


def test_pr_guard_flags_foreign_repo(monkeypatch):
    monkeypatch.setattr(pr_guard, "fetch_pr", lambda o, r, n: _fake_pr(owner="other", repo="repo"))
    body = client.post("/guard/pr", json={"url": "https://github.com/other/repo/pull/7"}).json()
    assert body["repo_matches_graph"] is False and body["graph_repo"] == settings.target_repo


@pytest.mark.parametrize("status", [404, 429, 502])
def test_pr_guard_maps_fetch_errors(monkeypatch, status):
    def boom(o, r, n):
        raise pr_guard.PRFetchError(status, "nope")

    monkeypatch.setattr(pr_guard, "fetch_pr", boom)
    res = client.post("/guard/pr", json={"url": "https://github.com/pallets/flask/pull/7"})
    assert res.status_code == status and res.json()["detail"] == "nope"


def test_pr_guard_rejects_bad_urls_before_any_network_call(monkeypatch):
    def must_not_run(*a):
        raise AssertionError("network call attempted")

    monkeypatch.setattr(pr_guard, "fetch_pr", must_not_run)
    for url in ["https://evil.example/pallets/flask/pull/7", "not a url at all"]:
        assert client.post("/guard/pr", json={"url": url}).status_code == 422
    assert client.post("/guard/pr", json={"url": "x" * 400}).status_code == 422


def _mock_github(monkeypatch, handler):
    real = httpx.Client
    monkeypatch.setattr(
        pr_guard.httpx,
        "Client",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )


def test_fetch_pr_parses_github_payloads(monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if request.url.path.endswith("/files"):
            return httpx.Response(
                200, json=[{"filename": "src/flask/app.py"}, {"filename": "README.md"}]
            )
        return httpx.Response(
            200,
            json={
                "title": "T",
                "body": None,
                "state": "closed",
                "merged": True,
                "user": {"login": "bob"},
                "html_url": "https://github.com/pallets/flask/pull/7",
                "additions": 3,
                "deletions": 1,
                "changed_files": 250,
            },
        )

    _mock_github(monkeypatch, handler)
    pr = pr_guard.fetch_pr("pallets", "flask", 7)
    assert set(seen) == {"api.github.com"}
    assert pr.state == "merged" and pr.author == "bob" and pr.body == ""
    assert pr.files == ["src/flask/app.py", "README.md"] and pr.truncated_files is True


@pytest.mark.parametrize("status,expected", [(404, 404), (403, 429), (429, 429), (500, 502)])
def test_fetch_pr_maps_http_errors(monkeypatch, status, expected):
    _mock_github(monkeypatch, lambda request: httpx.Response(status, json={}))
    with pytest.raises(pr_guard.PRFetchError) as err:
        pr_guard.fetch_pr("pallets", "flask", 7)
    assert err.value.status == expected


def test_fetch_pr_does_not_follow_redirects(monkeypatch):
    _mock_github(
        monkeypatch,
        lambda request: httpx.Response(302, headers={"location": "https://evil.example/x"}),
    )
    with pytest.raises(pr_guard.PRFetchError) as err:
        pr_guard.fetch_pr("pallets", "flask", 7)
    assert err.value.status == 502


# ------------------------------------------------------------------ LLM judge


class FakeClient:
    def __init__(self, text):
        self.models = SimpleNamespace(generate_content=lambda **kw: SimpleNamespace(text=text))


def judge(text):
    return guard.llm_judge("proposal", "Title", "Summary", "active", client=FakeClient(text))


def test_llm_judge_parses_and_clamps():
    out = judge(json.dumps({"verdict": "conflicts", "confidence": 7, "why": "undoes it"}))
    assert out == {"verdict": "conflicts", "confidence": 1.0, "why": "undoes it"}


@pytest.mark.parametrize(
    "text", ["not json", "{}", json.dumps({"verdict": "maybe"}), json.dumps({"verdict": None})]
)
def test_llm_judge_rejects_unusable_replies(text):
    assert judge(text) is None


def test_llm_judge_survives_client_errors():
    def boom(**kw):
        raise RuntimeError("quota")

    bad = SimpleNamespace(models=SimpleNamespace(generate_content=boom))
    assert guard.llm_judge("p", "t", "s", "active", client=bad) is None


def test_judge_proposal_prefers_llm_then_falls_back(monkeypatch):
    monkeypatch.setattr(
        guard,
        "_judge_client",
        lambda: FakeClient(json.dumps({"verdict": "aligns", "confidence": 0.9, "why": "ok"})),
    )
    result, name = guard.judge_proposal("p", "Title", "Summary", "active")
    assert name == "llm" and result["verdict"] == "aligns"

    monkeypatch.setattr(guard, "_judge_client", lambda: FakeClient("garbage"))
    _, name = guard.judge_proposal("p", "Title", "Summary", "active")
    assert name == "heuristic"

    monkeypatch.setattr(guard, "_judge_client", lambda: None)
    _, name = guard.judge_proposal("p", "Title", "Summary", "active")
    assert name == "heuristic"


def test_run_decision_guard_reports_judge(monkeypatch):
    monkeypatch.setattr(
        guard,
        "_judge_client",
        lambda: FakeClient(json.dumps({"verdict": "conflicts", "confidence": 0.8, "why": "x"})),
    )
    result = guard.run_decision_guard("Restore Python 3.6 helpers", ["src/flask/compat.py"])
    assert result["judge"] == "llm" and result["conflicts"]


def test_judge_prompt_marks_proposal_as_untrusted():
    assert "untrusted" in guard._JUDGE_PROMPT and "<proposal>" in guard._JUDGE_PROMPT
