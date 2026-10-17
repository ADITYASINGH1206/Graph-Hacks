# Demo, eval set, blog, submission

## 1. Three-minute demo video script & storyboard

| Time | On screen | Say |
|---|---|---|
| **0:00** | **Landing page hero** | Every team loses the why behind its decisions. The answer is buried in a thousand PR threads. Decision Archaeologist turns them into a graph you can ask. |
| **0:20** | **Scroll to How it works**, click the four steps | We ingest PRs and reviews, a model proposes decisions with exact quotes, we keep a quote only if it appears word for word in the source, and the agent walks the graph to answer. |
| **0:50** | **Ask page**: type *"Why was Python 3.6 dropped?"* | Watch the steps: it searches decisions, then traces to the source quote. The graph lights up the exact path it used. |
| **1:15** | Click **citation [1]**, then **View on GitHub** | Every claim links to a verified quote. Click it and you land on the real thread. This is the trust badge: one citation verified against the graph. |
| **1:35** | Ask: *"Why did Flask switch to Rust?"* | When there is no evidence it says so. It never invents a green answer. |
| **1:50** | **Timeline tab**, then **Time Machine** | Drag the date. See what was in force on any day, and what had already been replaced. |
| **2:10** | **PR Guard**: paste a real PR link (e.g. PR #4400 or #5000) | Before you merge, check a PR against past decisions. It shows the conflict, the quote, and who to ask. |
| **2:30** | **Risk map** | Where is knowledge fragile? Modules with few or inactive experts glow hot. |
| **2:45** | Back to the **Ask page graph** | The graph is the context layer. Every answer comes from FalkorDB traversals, not from model memory. Thanks. |

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
