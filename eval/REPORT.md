# Decision Archaeologist Evaluation Report

Generated: 2026-10-17T12:52:26.017183+00:00
Graph evaluated: `dig_pallets_flask` (4,138 nodes, 11,422 edges)
Agent mode: **live model (`gemini-flash-lite-latest`)**

## Summary Metrics
- **Total Questions Evaluated**: 12
- **Expected Decision Retrieval Rate**: 9/12 (75.0%)
- **Citation Validity Rate** (agent questions only): 90.0%
- **Average Latency**: 12530.4 ms

## Detailed Breakdown

| ID | Category | Question | Hit Expected Decision | Citation Validity | Tool Rounds | Latency (ms) |
|---|---|---|---|---|---|---|
| `q01` | **history** | Why was Python 3.6 dropped? | PASS | 100% | 3 | 3319.55 |
| `q02` | **history** | Why was Python 2 support dropped in Flask? | PASS | 100% | 4 | 5169.49 |
| `q03` | **history** | Why were async views and route handlers adopted? | PASS | 100% | 4 | 5067.58 |
| `q04` | **ownership** | Who is the primary maintainer and expert for flask/compat? | FAIL | 100% | 4 | 13993.88 |
| `q05` | **ownership** | Who decided to drop Python 3.6 support? | FAIL | 100% | 3 | 2689.61 |
| `q06` | **ownership** | Who are the most central engineers in Flask decision history? | PASS | 0% | 4 | 3970.8 |
| `q07` | **impact** | What modules and files were impacted by dropping Python 2? | FAIL | 100% | 5 | 5740.33 |
| `q08` | **impact** | What downstream releases included the Python 3.6 drop? | PASS | 100% | 3 | 97000.41 |
| `q09` | **reversal** | Has the Python 2 drop decision been superseded by a later decision? | PASS | 100% | 5 | 5502.2 |
| `q10` | **reversal** | What is the decision lineage starting from the Python 3.6 deprecation? | PASS | 100% | 5 | 5431.89 |
| `q11` | **guard** | Proposal: restore Python 3.6 compatibility helpers in src/flask/compat.py | PASS | n/a | n/a | 1305.58 |
| `q12` | **guard** | Proposal: modify compatibility layer touching previously superseded decisions | PASS | n/a | n/a | 1172.96 |

Guard rows (`guard` category) run graph queries only: they emit no citations and no tool rounds, so those columns are `n/a`.
