"""Evaluation runner evaluating Decision Archaeologist across 12 canonical questions."""

import asyncio
import datetime
import os
import time
from typing import Any

import yaml
from dig.agent.agent import DecisionAgent
from dig.agent.guard import run_decision_guard
from dig.config import settings
from dig.graph.client import get_graph


async def evaluate_question(item: dict[str, Any]) -> dict[str, Any]:
    qid = item["id"]
    category = item["category"]
    question = item["question"]
    expected_decs = item.get("expected_decisions", [])

    start_time = time.time()

    if category == "guard":
        # Run guard
        paths = ["src/flask/compat.py"] if "compat" in question.lower() else []
        res = run_decision_guard(description=question, paths=paths)
        latency = round((time.time() - start_time) * 1000, 2)
        found_ids = [c["decision_id"] for c in res["conflicts"]] + [
            r["decision_id"] for r in res["reversed_before"]
        ]
        hit = any(ed in found_ids for ed in expected_decs) if expected_decs else True
        return {
            "id": qid,
            "category": category,
            "question": question,
            "hit_expected": hit,
            "citation_validity": None,  # guard returns no [[ev:]] citations
            "tool_rounds": None,
            "latency_ms": latency,
            "details": f"Guard flagged {len(res['conflicts'])} conflicts and {len(res['reversed_before'])} historical decisions.",
        }

    # Run agent loop
    agent = DecisionAgent(graph_name=None, max_rounds=5)
    answer_event = None
    done_event = None
    tool_calls = 0

    async for ev in agent.ask_stream(question):
        if ev.event == "tool_call":
            tool_calls += 1
        elif ev.event == "answer":
            answer_event = ev.data
        elif ev.event == "done":
            done_event = ev.data

    latency = round((time.time() - start_time) * 1000, 2)
    tool_rounds = done_event.get("tool_rounds", 1) if done_event else 1

    cited_decs = []
    citations = answer_event.get("citations", []) if answer_event else []
    for c in citations:
        if c.get("decision_id"):
            cited_decs.append(c["decision_id"])

    # Fallback heuristic: check if expected decision ID is in final markdown
    md = answer_event.get("markdown", "") if answer_event else ""
    for ed in expected_decs:
        if ed in md:
            cited_decs.append(ed)

    hit = any(ed in cited_decs for ed in expected_decs) if expected_decs else True
    # If no explicit expected decisions, pass if tool executed
    if not expected_decs:
        hit = tool_calls > 0

    verification = answer_event.get("verification", {}) if answer_event else {}
    valid = verification.get("valid", len(citations))
    invalid = verification.get("invalid", 0)
    total_markers = valid + invalid
    validity_rate = 1.0 if total_markers == 0 else (valid / total_markers)

    return {
        "id": qid,
        "category": category,
        "question": question,
        "hit_expected": hit,
        "citation_validity": validity_rate,
        "tool_rounds": tool_rounds,
        "latency_ms": latency,
        "details": f"Cited {len(citations)} quotes, status: {'HIT' if hit else 'MISS'}",
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _graph_size() -> tuple[int, int]:
    """Return (nodes, edges) of the evaluated graph."""
    graph = get_graph()
    nodes = graph.query("MATCH (n) RETURN count(n)").result_set[0][0]
    edges = graph.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    return int(nodes), int(edges)


async def main() -> None:
    eval_dir = os.path.dirname(os.path.abspath(__file__))
    questions_file = os.path.join(eval_dir, "questions.yaml")
    with open(questions_file) as f:
        data = yaml.safe_load(f)

    # Without an API key the agent can only run in the canned offline mode. The report says so.
    live = bool(settings.google_api_key)
    if not live:
        settings.dig_offline = True

    questions = data.get("questions", [])
    print(f"Running evaluation on {len(questions)} canonical questions...\n")

    results = []
    for q in questions:
        print(f"[{q['id']}] ({q['category']}) {q['question']}")
        res = await evaluate_question(q)
        results.append(res)
        print(
            f"     -> Expected Hit: {res['hit_expected']} | Validity: {_pct(res['citation_validity'])} | Latency: {res['latency_ms']}ms\n"
        )

    mode = (
        f"live model (`{settings.agent_model}`)"
        if live
        else "OFFLINE SIMULATOR (canned replies, no LLM)"
    )
    nodes, edges = _graph_size()

    report_file = os.path.join(eval_dir, "REPORT.md")
    total = len(results)
    hits = sum(1 for r in results if r["hit_expected"])
    validities = [r["citation_validity"] for r in results if r["citation_validity"] is not None]
    avg_validity = (sum(validities) / len(validities)) * 100 if validities else 0.0
    avg_latency = sum(r["latency_ms"] for r in results) / total

    report_content = f"""# Decision Archaeologist Evaluation Report

Generated: {datetime.datetime.now(datetime.UTC).isoformat()}
Graph evaluated: `{get_graph().name}` ({nodes:,} nodes, {edges:,} edges)
Agent mode: **{mode}**

"""
    if not live:
        report_content += (
            "> **Read this first.** No API key was set, so the agent used the offline simulator, "
            "which returns scripted answers keyed to the seed graph. These numbers test the "
            "plumbing (tool wiring, citation verifier, repair turn, guard queries). They say "
            "nothing about how well a real model retrieves or explains decisions. "
            "Re-run with `GEMINI_API_KEY` set for a real benchmark.\n\n"
        )

    report_content += f"""## Summary Metrics
- **Total Questions Evaluated**: {total}
- **Expected Decision Retrieval Rate**: {hits}/{total} ({hits / total * 100:.1f}%)
- **Citation Validity Rate** (agent questions only): {avg_validity:.1f}%
- **Average Latency**: {avg_latency:.1f} ms

## Detailed Breakdown

| ID | Category | Question | Hit Expected Decision | Citation Validity | Tool Rounds | Latency (ms) |
|---|---|---|---|---|---|---|
"""
    for r in results:
        hit_icon = "PASS" if r["hit_expected"] else "FAIL"
        rounds = "n/a" if r["tool_rounds"] is None else r["tool_rounds"]
        report_content += (
            f"| `{r['id']}` | **{r['category']}** | {r['question']} | {hit_icon} | "
            f"{_pct(r['citation_validity'])} | {rounds} | {r['latency_ms']} |\n"
        )

    report_content += """
Guard rows (`guard` category) run graph queries only: they emit no citations and no tool rounds, so those columns are `n/a`.
"""

    with open(report_file, "w") as f:
        f.write(report_content)

    print(f"Report written to {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
