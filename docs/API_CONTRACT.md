# API contract (backend and frontend build against this in parallel)

Base URL `http://localhost:8000`. JSON unless stated. CORS enabled for `http://localhost:5173`.

## Shared shapes
```ts
type GraphNode = { id: string; label: string; title: string; props: Record<string, any> }
// id is the node uid, e.g. "Decision:dec_ab12cd34ef56", "PullRequest:1234", "Person:alice", "Module:flask/sessions"
type GraphEdge = { id: string; source: string; target: string; type: string; props: Record<string, any> }
type GraphElements = { nodes: GraphNode[]; edges: GraphEdge[] }

type Citation = { n: number; evidence_id: string; quote: string; url: string; author: string; ts: string; decision_id: string | null }
type Verification = { valid: number; invalid: number; repaired: boolean }
```

## GET /health
`{ "ok": true, "graph": "dig_pallets_flask", "counts": {"Decision": 0, "Evidence": 0, "Person": 0, "Issue": 0, "PullRequest": 0}, "last_synced": "ISO|null" }`

## POST /ask (SSE, `text/event-stream`)
Request: `{ "question": string, "user_id": string, "session_id": string|null }`

Events (each `event:` name with a JSON `data:` line):
| event | data |
|---|---|
| `recall` | `{ "findings": [{ "id": "", "summary": "", "ts": "" }] }` |
| `tool_call` | `{ "id": "", "name": "", "input": {} }` |
| `tool_result` | `{ "id": "", "name": "", "summary": "short text", "graph_elements": GraphElements }` |
| `token` | `{ "text": "" }` streamed answer text, markers already left as `[[ev:ID]]` |
| `answer` | `{ "markdown": "", "citations": Citation[], "path": GraphElements, "verification": Verification }` markers converted to `[1]`, `[2]` |
| `error` | `{ "message": "" }` |
| `done` | `{ "session_id": "", "tool_rounds": 0 }` |

## POST /guard
Request: `{ "description": string, "paths": string[] }`
Response:
```json
{ "conflicts": [{"decision_id":"","title":"","status":"","confidence":0.0,"why":"","evidence":[Citation],"people":["login"]}],
  "alignments": [{"decision_id":"","title":"","why":""}],
  "reversed_before": [{"decision_id":"","title":"","why":""}],
  "graph": GraphElements }
```

## GET /decisions
Query: `q?`, `module?`, `status?`, `type?`, `limit=50`. Returns `{ "items": [{id,title,type,status,decided_at,modules[],confidence}] }` for the timeline.

## GET /decisions/{id}
`{ "decision": {...}, "evidence": [Citation], "people": [{login, role}], "lineage": GraphElements, "impact": {...}, "stale": false }`

## GET /subgraph
Query: `center` (node uid), `depth=1..2`, `limit=80`. Returns `GraphElements`. Used when the user clicks a node.

## POST /sync
Triggers incremental sync in the background. Returns `{ "started": true }`. Poll `/health` for `last_synced`.

## GET /people/{login}
`{ "login": "", "modules": [{name, score}], "decisions": [{id,title,role}] }`

## Frontend behaviour contract
- Layout: left chat, centre Cytoscape canvas, right evidence panel; timeline tab under the canvas.
- On `tool_call`: show a pending chip. On `tool_result`: add `graph_elements` to the canvas with an entrance highlight and focus the newest nodes.
- On `answer`: replace the highlight with the final `path` (bold edges), render markdown, turn `[n]` into clickable chips that scroll the evidence panel to the quote and link to the source URL.
- Node click: call `/subgraph`, expand neighbours. Decision node click: load `/decisions/{id}` into the evidence panel.
- Status colours: active = green, superseded = amber, reversed = red; people = blue; modules = grey; evidence = hollow circle.
- Trust badge from `verification`: "All citations verified" when `invalid == 0`.
- Guard tab: textarea for proposal and paths, button "Check against past decisions", results as cards with evidence chips.
- Health bar shows counts and last sync; "Sync" button calls `/sync`.
