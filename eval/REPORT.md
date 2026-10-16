# Decision Archaeologist Evaluation Report

Generated: 2026-10-16T15:56:12.296129+00:00
Graph Evaluated: `pallets/flask` (FalkorDB)

## Summary Metrics
- **Total Questions Evaluated**: 12
- **Expected Decision Retrieval Rate**: 12/12 (100.0%)
- **Citation Validity Rate**: 100.0%
- **Average Latency**: 20.9 ms

## Detailed Breakdown

| ID | Category | Question | Hit Expected Decision | Citation Validity | Tool Rounds | Latency (ms) |
|---|---|---|---|---|---|---|
| `q01` | **history** | Why was Python 3.6 dropped? | PASS | 100% | 3 | 30.88 |
| `q02` | **history** | Why was Python 2 support dropped in Flask? | PASS | 100% | 3 | 13.74 |
| `q03` | **history** | Why were async views and route handlers adopted? | PASS | 100% | 3 | 9.63 |
| `q04` | **ownership** | Who is the primary maintainer and expert for flask/compat? | PASS | 100% | 2 | 8.57 |
| `q05` | **ownership** | Who decided to drop Python 3.6 support? | PASS | 100% | 2 | 8.88 |
| `q06` | **ownership** | Who are the most central engineers in Flask decision history? | PASS | 100% | 2 | 123.33 |
| `q07` | **impact** | What modules and files were impacted by dropping Python 2? | PASS | 100% | 2 | 10.68 |
| `q08` | **impact** | What downstream releases included the Python 3.6 drop? | PASS | 100% | 3 | 12.75 |
| `q09` | **reversal** | Has the Python 2 drop decision been superseded by a later decision? | PASS | 100% | 2 | 10.69 |
| `q10` | **reversal** | What is the decision lineage starting from the Python 3.6 deprecation? | PASS | 100% | 2 | 10.42 |
| `q11` | **guard** | Proposal: restore Python 3.6 compatibility helpers in src/flask/compat.py | PASS | 100% | 1 | 5.89 |
| `q12` | **guard** | Proposal: modify compatibility layer touching previously superseded decisions | PASS | 100% | 1 | 5.04 |

## Key Observations
1. **Provenance Grounding**: Citation verification achieved 100% validity post-repair turn. Hallucinated and unverified IDs are intercepted and sanitized before rendering to user.
2. **Decision Guard Performance**: Guard mode detects conflicts in <50ms with zero network calls when querying the local FalkorDB graph.
3. **Lineage Traversal**: The `SUPERSEDES` and `REVERSES` chain reliably traces backwards across version milestones.
