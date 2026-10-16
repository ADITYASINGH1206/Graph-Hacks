# Decision Archaeologist Evaluation Report

Generated: 2026-10-16T16:12:37.661116+00:00
Graph evaluated: `dig_pallets_flask` (22 nodes, 32 edges)
Agent mode: **OFFLINE SIMULATOR (canned replies, no LLM)**

> **Read this first.** No API key was set, so the agent used the offline simulator, which returns scripted answers keyed to the seed graph. These numbers test the plumbing (tool wiring, citation verifier, repair turn, guard queries). They say nothing about how well a real model retrieves or explains decisions. Re-run with `GEMINI_API_KEY` set for a real benchmark.

## Summary Metrics
- **Total Questions Evaluated**: 12
- **Expected Decision Retrieval Rate**: 12/12 (100.0%)
- **Citation Validity Rate** (agent questions only): 100.0%
- **Average Latency**: 22.0 ms

## Detailed Breakdown

| ID | Category | Question | Hit Expected Decision | Citation Validity | Tool Rounds | Latency (ms) |
|---|---|---|---|---|---|---|
| `q01` | **history** | Why was Python 3.6 dropped? | PASS | 100% | 3 | 49.7 |
| `q02` | **history** | Why was Python 2 support dropped in Flask? | PASS | 100% | 3 | 9.64 |
| `q03` | **history** | Why were async views and route handlers adopted? | PASS | 100% | 3 | 10.1 |
| `q04` | **ownership** | Who is the primary maintainer and expert for flask/compat? | PASS | 100% | 2 | 8.18 |
| `q05` | **ownership** | Who decided to drop Python 3.6 support? | PASS | 100% | 2 | 7.82 |
| `q06` | **ownership** | Who are the most central engineers in Flask decision history? | PASS | 100% | 2 | 128.9 |
| `q07` | **impact** | What modules and files were impacted by dropping Python 2? | PASS | 100% | 2 | 14.57 |
| `q08` | **impact** | What downstream releases included the Python 3.6 drop? | PASS | 100% | 3 | 9.06 |
| `q09` | **reversal** | Has the Python 2 drop decision been superseded by a later decision? | PASS | 100% | 2 | 8.92 |
| `q10` | **reversal** | What is the decision lineage starting from the Python 3.6 deprecation? | PASS | 100% | 2 | 7.59 |
| `q11` | **guard** | Proposal: restore Python 3.6 compatibility helpers in src/flask/compat.py | PASS | n/a | n/a | 5.05 |
| `q12` | **guard** | Proposal: modify compatibility layer touching previously superseded decisions | PASS | n/a | n/a | 4.01 |

Guard rows (`guard` category) run graph queries only: they emit no citations and no tool rounds, so those columns are `n/a`.
