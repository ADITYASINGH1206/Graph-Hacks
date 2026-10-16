# Why Did We Do It This Way? Giving an Agent a Graph of Every Decision

> *How we built Decision Archaeologist for Graph Hacks Track 3 (Company Brain) using FalkorDB and Google Gemini.*

---

## 1. The Graveyard of Lost Context
Every engineering team has stared at a puzzling block of code and asked: *"Why on earth did they build it like this?"*

Git blame only answers **what** lines changed and **when**. But the critical **why**—the trade-offs debated, the edge cases discovered, the alternative approaches rejected, and the historical reversions—is scattered across hundreds of closed GitHub issues, thousand-comment PR threads, and people's heads.

When new engineers join or when autonomous coding agents generate code, they lack this institutional memory. The result? They unknowingly repeat mistakes that were already tried and reversed three years ago.

## 2. Why a Graph?
Traditional RAG systems embed raw issue texts or code snippets into flat vector databases. But questions about architecture are inherently multi-hop graph questions:
- *"Who has the most recency-weighted expertise in the module affected by this decision?"*
- *"What earlier decision did this change supersede, and has it been reversed since?"*
- *"If I change this API, what downstream releases and decisions depend on it?"*

A graph database like **FalkorDB** is uniquely suited for this. Decisions are nodes; provenance, code files, engineers, releases, and evolutionary relationships (`SUPERSEDES`, `REVERSES`, `DEPENDS_ON`) are typed edges. A single Cypher query traverses years of decision lineage in sub-milliseconds.

---

## 3. The Anti-Hallucination Pipeline
LLMs are notorious for inventing plausible-sounding rationale. We engineered a strict 4-stage pipeline where no decision or citation enters the system without cryptographic and string-level verification:

```
[GitHub Threads]
       │
       ▼ (Signal Scoring: labels + keywords + reviews)
[Qualifying Candidates]
       │
       ▼ (Gemini Extraction: structured JSON)
[Extracted Claims]
       │
       ▼ (Quote Verification: whitespace & quote normalization)
[FalkorDB Knowledge Graph]
```

1. **Signal Filter**: Scores threads based on labels (`breaking`, `deprecation`), keyword stems, and review comment volume.
2. **Structured Extraction**: Gemini extracts the core choice, rationale, and exact verbatim quotes from the discussion.
3. **Exact Substring Verification**: The extractor tests every quoted claim against the raw thread body on disk. If a single character is hallucinated, the quote is rejected.
4. **Semantic Linking**: A classifier links decisions into evolutionary chains (`SUPERSEDES`, `REVERSES`, `DEPENDS_ON`, `CONFLICTS_WITH`) with confidence scores.

---

## 4. FalkorDB Schema & Core Cypher Queries

### The Knowledge Graph Schema
- `(:Decision)`: `id`, `title`, `summary`, `type`, `status`, `decided_at`, `confidence`
- `(:Evidence)`: `id`, `quote`, `url`, `author`, `ts`
- `(:Person)`: `login`, `name`, `avatar_url`
- `(:Module)`: `name`
- `(:PullRequest)`, `(:Issue)`, `(:Release)`, `(:File)`

### Query 1: Tracing Historical Decision Lineage
Traverse the variable-length chain of superseded or reversed decisions:
```cypher
MATCH path = (start:Decision {id: $decision_id})-[:SUPERSEDES|REVERSES*1..6]->(older:Decision)
RETURN path
```

### Query 2: Recency-Decay Expertise Scoring
Calculate engineer familiarity based on authored PRs and reviews decayed by age:
```cypher
MATCH (p:Person)-[k:KNOWS]->(m:Module {name: $module})
RETURN p.login, k.score, k.authored, k.reviewed, k.commented
ORDER BY k.score DESC LIMIT 5
```

---

## 5. Decision Guard: From Knowledge to Active Protection
Most knowledge bases are passive documentation that nobody reads. We created **Decision Guard**:
Whenever a developer opens a PR or plans an architectural change, Decision Guard checks the proposal against historical decisions in <50ms:

```json
{
  "conflicts": [
    {
      "decision_id": "dec_drop_py36",
      "title": "Drop Python 3.6 support",
      "status": "active",
      "why": "Proposal re-introduces compatibility helpers for Python 3.6 which were explicitly dropped in PR #4400.",
      "people": ["davidism"]
    }
  ]
}
```
Decision Guard flags the conflict, cites the original GitHub PR evidence, and suggests the original deciders (`@davidism`) as natural reviewers!

---

## 6. The Citation Verifier & Trust Badge
During agent query turns, the model generates responses with inline evidence markers `[[ev:ID]]`.
The backend `CitationVerifier`:
1. Compares all markers against evidence IDs returned by tools in *that specific turn*.
2. Catches hallucinated IDs or uncited factual claims.
3. Executes a 1-turn repair prompt: *"These claims lack valid evidence: [...]. Rewrite using only tool-returned evidence IDs."*
4. Converts verified markers to clickable `[1]`, `[2]` citation chips linking directly to GitHub source comments.
5. Emits a trust badge: **"All citations verified against graph"**.

---

## 7. Real Evaluation Benchmark Results
We evaluated Decision Archaeologist across 12 canonical questions in `eval/questions.yaml` covering History, Ownership, Impact, Reversal, and Guard modes:

| Metric | Result |
|---|---|
| **Total Questions Evaluated** | 12 |
| **Expected Decision Retrieval Rate** | **100.0%** (12/12) |
| **Citation Validity Rate** | **100.0%** (after verification) |
| **Average Query Latency** | **20.9 ms** |
| **Real Repository Tested** | `pallets/flask` (4,133 nodes, 10,233 edges) |

---

## 8. What We Would Build Next
1. **Multi-Source Ingestion**: Ingest Slack architecture channels, Google Docs design specs, and Notion RFCs into the same decision graph.
2. **Automated ADR Sync**: Automatically open a Pull Request creating a `docs/adr/ADR-xxxx.md` file whenever a high-signal decision is detected.
3. **IDE Integration**: A VSCode / Cursor extension that underlines deprecated code patterns in the editor and explains *why* it was deprecated with a link to the original PR debate.

---

*Decision Archaeologist turns software history from a forgotten archive into an active, protective co-pilot.*
