# Build plan and coding-agent prompts

Times are IST. Deadline: **Sun 18 Oct 23:59**. Plan to submit by Sun 20:00 and keep the last hours as buffer.

## Timeline
| Window | Goal | Prompts |
|---|---|---|
| Fri 19:30 to 23:30 | Repo scaffold, FalkorDB up, schema, GitHub ingest running in the background | P0, P1, P2 |
| Sat 00:00 to 09:00 | Sleep. Ingest runs; extraction can start in the morning | |
| Sat 09:00 to 13:00 | Loader, extraction + verification, linking, expertise | P3, P4, P5 |
| Sat 13:00 to 19:00 | Tools, MCP server, agent loop, verifier, API | P6, P7, P8 |
| Sat 14:00 to 21:00 (parallel) | Frontend against the API contract with mock data | P9 |
| Sun 09:00 to 13:00 | Guard, memory, sync, graph canvas polish | P10 |
| Sun 13:00 to 15:00 | Eval, README, bug-fix, **feature freeze at 15:00** | P11 |
| Sun 15:00 to 20:00 | Demo video, blog post, submission | P12 |

If you fall behind, cut in this order: memory, ADR drafting, community view, timeline, `find_path`, `central_people`.

## Parallelisation (Claude Code worktrees or separate sessions)
Contracts are fixed in `GRAPH_SCHEMA.md` and `API_CONTRACT.md`, so these can run at once after P1:
- **Lane A (data):** P2, P3, P4, P5
- **Lane B (agent/API):** P6, P7, P8 using a tiny hand-written seed graph (script in P6) until Lane A finishes
- **Lane C (UI):** P9 against a mock server that replays canned SSE events

Merge lanes Sat evening, then run the end-to-end check in P8's acceptance test with the real graph.

## Kickoff habit
Before each prompt tell the agent: "Read CLAUDE.md and the docs referenced below first. Work only on this task. When done, show how you verified each acceptance criterion." Use plan mode for P6 and P7.

---

## P0: Scaffold
```
Read CLAUDE.md and docs/ARCHITECTURE.md.

Task: scaffold the repository exactly per the layout in CLAUDE.md.
- pyproject.toml (backend package `dig`, deps: fastapi, uvicorn, httpx, pydantic, falkordb,
  anthropic, mcp, networkx, pyyaml, tenacity, pytest, pytest-asyncio, ruff)
- docker-compose.yml: falkordb/falkordb:latest, ports 6379 and 3000, named volume
- .env.example from ARCHITECTURE.md section 8; .gitignore (data/, .env, node_modules, __pycache__)
- backend/dig/config.py using pydantic-settings
- backend/dig/cli.py with Typer commands as stubs: ingest, extract, link, score, sync, serve
- backend/dig/graph/client.py: get_graph(name) returning a falkordb Graph, plus a health check
- Vite React TS app in frontend/ with Cytoscape installed (empty shell)
- One passing test that connects to FalkorDB and runs RETURN 1

Acceptance: `docker compose up -d falkordb`, `pytest -q` passes, `dig --help` lists the commands,
`npm run dev` serves the shell. Do not implement features beyond this.
```

## P1: Graph layer
```
Read CLAUDE.md and docs/GRAPH_SCHEMA.md.

Task: implement backend/dig/graph/schema.py and queries.py.
- schema.py: ensure_schema(graph) creating the indexes in GRAPH_SCHEMA.md. Check the FalkorDB docs
  for exact index and full-text syntax and tell me what you verified. Add a `uid` property
  convention (<Label>:<key>) set on every node at load time.
- queries.py: one function per core query in GRAPH_SCHEMA.md (search_decisions, get_decision,
  lineage, who_knows, impact, active_decisions_for_modules, shortest_path). All parameterised,
  each returning pydantic models plus a GraphElements object (nodes and edges touched).
- A seed script backend/scripts/seed_demo_graph.py that loads ~40 hand-written nodes/edges
  (3 decisions with a supersede chain, 5 people, 3 modules, evidence with quotes) so other lanes
  can work without real data.

Acceptance: pytest covers each query against the seed graph; a table of query name -> rows returned
is printed by `python -m dig.graph.queries --demo`.
```

## P2: GitHub ingest
```
Read CLAUDE.md and docs/INGESTION_AND_EXTRACTION.md sections 1 and 8.

Task: implement ingest/github.py, normalize.py, cache.py and `dig ingest`.
- Async httpx client with token auth, pagination, rate-limit handling (sleep until reset),
  disk cache under data/raw keyed by id and updated_at.
- Fetch issues and PRs (with comments, reviews, review comments, changed files), releases.
- Normalise into the Thread/Block models with the block id format given in the doc.
- CLI: `dig ingest --repo OWNER/REPO --max-threads 1500` with progress logging.
- Unit tests with recorded fixtures (no network in tests).

Acceptance: running against a small repo for 30 threads produces data/raw files and a normalised
threads.jsonl; re-running makes zero network calls for unchanged threads (show the log).
Run the real ingest for TARGET_REPO in the background and report counts when done.
```

## P3: Loader
```
Read CLAUDE.md, docs/GRAPH_SCHEMA.md, docs/INGESTION_AND_EXTRACTION.md section 5.

Task: implement graph/loader.py and `dig load-structure` (add to CLI).
- Load Person, Issue, PullRequest, Release, File, Module and the structural edges
  (AUTHORED, REVIEWED, COMMENTED_ON, CLOSES, REFERENCES, TOUCHES, IN_MODULE, SHIPPED_IN).
- Module derived from file path at MODULE_DEPTH. SHIPPED_IN: first release after merged_at, unless
  release notes cite the PR number.
- Use UNWIND batches of 500, MERGE on keys, set uid on all nodes. Idempotent.

Acceptance: loading twice leaves node/edge counts unchanged (show counts); print counts per label
and edge type; a sample Cypher showing a PR with its files, module and release.
```

## P4: Decision extraction and verification
```
Read CLAUDE.md and docs/INGESTION_AND_EXTRACTION.md sections 2, 3, 4.

Task: implement extract/signals.py, prompts.py, extractor.py, verify.py and `dig extract`.
- Signal scoring per the doc, with a --threshold flag and a report of how many threads qualify.
- Extractor: EXTRACT_MODEL, temperature 0, JSON only, asyncio.Semaphore(8), content-hash disk cache,
  one retry on bad JSON. Use the exact system prompt in the doc.
- verify.py: whitespace and quote-normalised substring check against the cited block. Drop unverified
  evidence, drop decisions with none left. Return stats.
- Write results to data/extracted/decisions.jsonl and load them with graph/loader.py
  (Decision, Evidence, DECIDED_IN, SUPPORTED_BY, MADE, AFFECTS, Concept).
- Tests: verifier unit tests (exact match, curly quotes, hallucinated quote rejected).

Acceptance: print N threads sent, decisions extracted, evidence kept/dropped, and 5 random decisions
with their verified quotes. Show the Decision count in FalkorDB.
```

## P5: Linking and expertise
```
Read CLAUDE.md and docs/INGESTION_AND_EXTRACTION.md sections 6 and 7.

Task: implement extract/linker.py, extract/expertise.py, `dig link` and `dig score`.
- Candidate pair generation from shared Module/Concept and cross-references, capped at 600.
- Pair classification via EXTRACT_MODEL with JSON output and caching; write edges at confidence >= 0.6.
- Explicit revert detection from PR titles/bodies ("Revert", "This reverts #n") before the LLM pass.
- Update status and valid_to on superseded/reversed decisions.
- Expertise scoring per the doc, bots excluded, writes KNOWS edges.

Acceptance: report counts by relation type; show three real supersede/reverse chains with titles and
dates; show the top 5 people for two modules with their component counts.
```

## P6: Tools and MCP server
```
Read CLAUDE.md, docs/AGENT_AND_TOOLS.md (sections 1, 2, 7) and docs/GRAPH_SCHEMA.md.
Use plan mode first and show the plan.

Task: implement agent/tools.py and mcp_server.py.
- Each tool in the catalogue (except check_proposal, draft_adr, recall, pin which come later) as a
  typed function with pydantic input/output and a JSON schema, returning data plus graph_elements.
- A registry used by both the agent loop and the FastMCP server; no duplicated logic.
- central_people: first check docs.falkordb.com for algorithm procedures; if PageRank/betweenness is
  not available, implement it with networkx on an exported subgraph (graph/algos.py), same interface.
- Tests against the seed graph from P1.

Acceptance: `python -m dig.mcp_server` starts; list its tools; call two of them through an MCP client
and show output. State which algorithm path (native or networkx) you used.
```

## P7: Agent loop and verifier
```
Read CLAUDE.md and docs/AGENT_AND_TOOLS.md sections 1, 3, 4. Use plan mode first.

Task: implement agent/agent.py, prompts.py, verifier.py.
- Tool-use loop with AGENT_MODEL, max 8 rounds, parallel tool calls allowed, async generator yielding
  the SSE events in docs/API_CONTRACT.md.
- Use the system prompt from the doc verbatim (fill {repo}).
- Verifier: evidence-id set from tool results, marker parsing, factual-sentence heuristic, one repair
  turn, stripping of invalid markers, Citation list construction.
- Tests with a fake model client: valid citations pass; an invented evidence id is caught and repaired.

Acceptance: a CLI `dig ask "Why was X deprecated?"` prints tool calls, then the answer with numbered
citations and the verification badge, using the real graph. Show one deliberately failing case
(inject a bad marker) being repaired.
```

## P8: FastAPI and SSE
```
Read CLAUDE.md and docs/API_CONTRACT.md.

Task: implement api/main.py, models.py, sse.py and `dig serve`.
- All endpoints in the contract. /ask streams events exactly as specified. /guard can return an empty
  result until P10. CORS for :5173.
- Pydantic response models match the contract; add an OpenAPI check test.
- End-to-end test: with the real graph, POST /ask and assert event order recall? -> tool_call ->
  tool_result -> token* -> answer -> done, and that every citation url is non-empty.

Acceptance: curl -N examples for /health and /ask in the README; the e2e test passes.
```

## P9: Frontend
```
Read CLAUDE.md and docs/API_CONTRACT.md (the "Frontend behaviour contract" section).
Build against a mock server first: frontend/mock/server.ts replaying canned SSE events, switchable
with VITE_MOCK=1.

Task: React + TypeScript + Cytoscape UI.
- Three-pane layout (chat | graph | evidence) with a timeline tab and a Guard tab.
- Consume SSE with fetch + ReadableStream. Show tool chips, stream tokens, animate nodes/edges onto
  the canvas as tool_result events arrive, then bold the final path.
- Citation chips scroll the evidence panel and link to the source URL. Trust badge from verification.
- Node click expands neighbours via /subgraph; decision click loads /decisions/{id}.
- Status colours per the contract; a legend; dark theme; readable at 1280x720 for screen recording.
- Health bar with counts, last sync, Sync button.

Acceptance: with VITE_MOCK=1 the full flow works; switching to the real API works with no code change
except the base URL. Provide screenshots of the idle and answered states.
```

## P10: Guard, freshness, memory
```
Read CLAUDE.md and docs/AGENT_AND_TOOLS.md sections 5 and 6, docs/INGESTION_AND_EXTRACTION.md section 8.

Task:
1. Decision Guard (agent/guard.py, tool check_proposal, POST /guard) per the doc.
2. `dig sync` incremental: since-based fetch, re-extract changed threads only, link new decisions,
   recompute expertise, set Meta.last_synced; staleness flag on /decisions/{id}.
3. Memory graph mem_<user_id> with Question/Finding/Pin, recall injection at the start of /ask, the
   `recall` and `pin` tools, and the `recall` SSE event.
4. draft_adr tool (Markdown ADR with links to evidence).

Acceptance: demo transcripts showing (a) a proposal that conflicts with an active decision and one
that touches a previously reversed decision, (b) sync picking up a changed thread and the answer
changing, (c) restarting the server and the agent recalling an earlier finding.
```

## P11: Eval, hardening, README
```
Read CLAUDE.md and docs/DEMO_AND_BLOG.md section 2.

Task:
- eval/questions.yaml: 12 questions I will provide categories for (history, ownership, impact,
  reversal, guard) plus expected decision ids after you inspect the real graph; propose candidates
  from the data and I will confirm.
- eval/run_eval.py: runs each question, reports (a) answer cites at least one expected decision,
  (b) citation validity rate, (c) tool rounds, (d) latency. Output a Markdown table to eval/REPORT.md.
- Fix the top 3 failures found.
- README: what it is, architecture diagram, setup in 5 commands, tool list, limitations, how
  provenance is enforced.

Acceptance: eval/REPORT.md generated; citation validity is 100% after repair; README quickstart works
from a clean clone (verify).
```

## P12: Demo and submission helpers
```
Read docs/DEMO_AND_BLOG.md.

Task:
- A `scripts/demo_reset.sh` that starts FalkorDB, loads cached data (no network), and warms the cache
  for the 5 demo questions.
- Add an `--offline` flag so LLM calls are served from cache when present.
- Draft the blog post from the outline using real numbers from eval/REPORT.md and the graph counts.
- Produce a one-page submission text (problem, solution, how FalkorDB is used, tracks, links).

Acceptance: demo_reset.sh followed by the 5 demo questions works with the network disabled.
```
