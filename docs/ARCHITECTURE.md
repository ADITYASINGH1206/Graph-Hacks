# Architecture

## 1. What we are building
A knowledge agent for one open-source project ("the company"). Raw material is public: issues, PRs, review comments, commits touching files, release notes. The system turns that into a graph where **decisions are first-class nodes** with provenance, then exposes graph operations as tools an LLM agent calls to answer questions and do work.

## 2. Why this wins the track
| Track 3 focus (from the brief) | How we meet it |
|---|---|
| Docs, tickets, chats in one graph | Issues, PRs, reviews, release notes, file paths in one graph |
| Who owns what, who knows what | `KNOWS` edges scored from authored/reviewed/commented work per module, with recency decay |
| Tracing decisions to their source | `Decision -[:SUPPORTED_BY]-> Evidence {quote,url}` and `trace_to_source` tool |
| Keeping knowledge current | Incremental `sync`, supersede/reverse edges, `valid_to`, staleness badge in UI |
| Answers with clear sources | Citation verifier rejects any claim whose evidence id was not returned by a tool this turn |
| Gets work done | **Decision Guard** (checks a proposed change against active decisions) and **ADR drafting** |

Bonus for Track 2 overlap: per-user memory graph (`mem_<user>`) that stores findings and pins across sessions.

## 3. Component diagram
```
 GitHub REST API ──► ingest/github.py ──► data/raw/*.json (cache)
                                  │
                                  ▼
                      extract/signals.py  (cheap filter: which threads likely hold decisions)
                                  │
                                  ▼
            extract/extractor.py (Haiku, JSON) ──► extract/verify.py (quote ⊂ source)
                                  │
                                  ▼
          graph/loader.py (MERGE nodes+edges) ◄── extract/linker.py (SUPERSEDES/REVERSES/…)
                                  │             ◄── extract/expertise.py (KNOWS scores)
                                  ▼
                       FalkorDB  graph dig_<owner>_<repo>
                         ▲                 ▲
                         │ Cypher          │ algos (PageRank, BFS, …)
                 agent/tools.py ───────────┘
                         ▲
        ┌────────────────┴───────────────┐
        │ mcp_server.py (same tools,     │  agent/agent.py (Sonnet tool-use loop)
        │ for any MCP client)            │  agent/verifier.py (citation check)
        └────────────────────────────────┘  agent/memory.py (mem_<user> graph)
                                            agent/guard.py (Decision Guard)
                                  ▲
                          api/main.py (FastAPI, SSE)
                                  ▲
                    frontend (chat | graph canvas | evidence panel | timeline)
```

## 4. Data flow for one question
1. UI sends `POST /ask {question, user_id}`; server opens an SSE stream.
2. Agent loads recall context from `mem_<user>` (top 3 related past findings).
3. Sonnet picks tools. Each call is validated, run against FalkorDB, and returns compact JSON plus `graph_elements`. The server streams `tool_call` and `tool_result` events, so the UI highlights the path as it forms.
4. Sonnet writes the answer with `[[ev:ID]]` citation markers.
5. Verifier checks every cited id appeared in this turn's tool results; unsupported claims trigger one repair turn, then get flagged.
6. Final event carries `answer`, `citations` (id, quote, url), and `path` (ordered nodes/edges). The server writes a `Finding` to `mem_<user>`.

## 5. Key design decisions
- **Decisions are extracted at ingest, not at query time.** Query-time LLM reading of raw threads is just RAG. Pre-extracted, linked decisions let the agent do multi-hop traversal (lineage, impact, expertise) in a handful of Cypher calls.
- **Provenance is enforced in code.** The LLM cannot create evidence; only the extractor can, and only after substring verification.
- **Expertise is computed, not guessed.** Python aggregates activity per person per module, applies weights and decay, writes `KNOWS {score}`. The agent only reads it.
- **Modules derive from paths.** `File` path prefix at depth 2 (configurable) becomes `Module`. Cheap, deterministic, good enough.
- **MCP surface.** Tools are plain Python functions registered both in the agent loop and in a FastMCP server, so the same graph tools work from any MCP client. This satisfies the "tool selection through MCP" theme.
- **Multi-graph.** Project graph and per-user memory graph are separate graphs on one FalkorDB instance.

## 6. Scope cut line
**Must (Fri night to Sat midday):** ingest, extraction with verification, graph load, tools `search_decisions`, `get_decision`, `trace_to_source`, `decision_lineage`, `who_knows`, agent loop with citations, minimal chat UI.

**Should (Sat to Sun morning):** graph canvas with path highlighting, `impact_of`, `find_path`, `central_people`, Decision Guard, timeline, incremental sync + staleness badge, eval script.

**Could (Sun, only if ahead):** memory graph with `recall`, ADR drafting, MCP server demo from Claude Desktop, community detection view.

**Won't:** auth, multi-repo UI, webhooks, fine-tuning, vector DB.

## 7. Risks and mitigations
| Risk | Mitigation |
|---|---|
| GitHub rate limits | Token auth (5000/hr), disk cache, cap threads at ~1500 |
| Extraction cost/time | Haiku, signal filter first, concurrency 8, content-hash cache |
| LLM hallucinated quotes | Substring verification; drop unverified |
| Sparse decision links | Candidate-pair linking from shared modules and cross-references; accept lower recall, show confidence |
| FalkorDB procedure mismatch | Check docs; Python fallback |
| Demo fails live | Pre-record video; cached data; `--offline` mode that reads cached LLM results |
| Time overrun | Cut line above; freeze features Sun 15:00 IST |

## 8. Environment variables
```
GITHUB_TOKEN=
ANTHROPIC_API_KEY=
AGENT_MODEL=claude-sonnet-5-5
EXTRACT_MODEL=claude-haiku-5-5
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
TARGET_REPO=pallets/flask
MODULE_DEPTH=2
```
