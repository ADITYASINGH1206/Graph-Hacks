# Demo, eval set, blog, submission

## 1. Three-minute demo script
Screen: graph canvas centre, chat left, evidence right, 1280x720, dark theme.

| Time | Beat | What to show |
|---|---|---|
| 0:00 | Problem | One line: "Teams lose the why behind decisions. Agents only see single records." |
| 0:15 | The graph | FalkorDB Browser for 5 seconds: Decision, Evidence, Person, Module nodes |
| 0:30 | History question | "Why was X deprecated and who decided it?" Watch tool chips and the path draw itself; click a citation, land on the real GitHub quote |
| 1:05 | Lineage | "Has that decision been reversed or replaced?" Lineage chain lights up, status colours change |
| 1:30 | Ownership | "Who actually knows module Y?" Answer explains authored/reviewed/commented and recency |
| 1:55 | Decision Guard | Paste a realistic proposal; the guard flags a conflicting past decision with the original deciders as suggested reviewers |
| 2:25 | Freshness and memory | Run sync (cached "new" PR), re-ask, answer changes; restart server, the agent recalls the earlier finding |
| 2:45 | Trust | Point at the "all citations verified" badge: the model cannot cite what the graph did not return |
| 2:55 | Close | Tracks covered, tools exposed over MCP, repo link |

Pick demo questions only after inspecting the real graph; choose ones with a visible supersede/reverse chain and a clear module owner.

## 2. Eval set (`eval/questions.yaml`)
Twelve questions, three per category, expected decision ids filled in after you inspect the data:
- **History:** why was a feature deprecated/removed/adopted
- **Ownership:** who knows a module, who reviewed its big changes
- **Impact/reversal:** what a decision affected; was it later replaced or reverted
- **Guard:** two proposals, one conflicting and one clean

Metrics reported in `eval/REPORT.md`: cites an expected decision (%), citation validity before and after repair (%), average tool rounds, median latency, extraction stats (threads sent, decisions kept, evidence dropped by verification). These numbers go in the blog.

## 3. Blog post outline (side prize: AirPods 5)
Title idea: *"Why did we do it this way? Giving an agent a graph of every decision."*
1. The problem: answers live across issues, PRs, and people's heads
2. Why a graph: decisions as nodes, provenance as edges, one query for multi-hop questions
3. Pipeline: thread signals, LLM extraction, quote verification (the anti-hallucination step), linking
4. Schema diagram and two Cypher snippets (lineage, who-knows)
5. The agent: tools as graph operations, MCP, citation verifier with a before/after example
6. Decision Guard: from knowledge to action
7. Freshness and memory across sessions
8. Results: eval table, counts, one failure and how we fixed it
9. What we would build next (more repos, Slack/Notion sources, ADR automation)
Keep it concrete: real numbers, a real screenshot per section, link to the repo and demo video.

## 4. Submission checklist
Read the Rules tab first (it was collapsed in what you shared) and confirm each item:
- [ ] Registered; team members added or solo confirmed
- [ ] Allowed to reuse prior code? If you reuse any, say which parts are new
- [ ] Coding assistants allowed? Disclose use if required
- [ ] Track(s) selected; whether entering several tracks at once is allowed
- [ ] Deployment required? If so, a hosted demo plus the video as fallback
- [ ] Public repo with README, setup, `.env.example`, no secrets in history
- [ ] Demo video under the length limit, link works logged out
- [ ] Blog post published and linked in the submission for the side prize
- [ ] Submission text names FalkorDB usage: multigraph, full-text, algorithms, MCP
- [ ] Submitted before Sun 20:00 IST; confirm the confirmation email or page state

## 5. Submission text (fill in)
- **One line:** An agent that explains why a project made its decisions, who knows what, and what a new change would contradict, with every claim traced to a verified source quote.
- **Problem:** Context about decisions is scattered and agents cannot trace it.
- **Solution:** FalkorDB graph of decisions, evidence, people, modules, releases; extraction with quote verification; tool-using agent over MCP; Decision Guard; sync and memory.
- **How FalkorDB is used:** per-project and per-user graphs, full-text index, multi-hop traversals, graph algorithms, streamed path visualisation.
- **Track:** 03 Company Brain (with Track 02 memory features if multi-track entry is allowed).
- **Links:** repo, demo video, blog post.
