# Track 3: Company Brain - Decision Archaeologist

## 1. Problem
Codebases are Graveyards of Forgotten Context. While Git preserves *what* lines of code changed, the critical reasoning—*why* an architecture choice was made, *who* debated and decided it, and *what past attempts failed or were reversed*—remains buried across thousands of closed GitHub issues, PR discussion comments, and design proposals. When engineers propose changes, they inevitably repeat past mistakes or contradict forgotten architectural principles.

## 2. Solution: Decision Archaeologist
Decision Archaeologist is a graph-native context engine that turns repository history into an active, verifiable knowledge brain powered by **FalkorDB** and **Google Gemini**:
- **Strict Evidence-Grounded Extraction**: Extracts decisions and links them directly to verbatim GitHub discussion quotes with verified URL provenance. Hallucinated quotes are systematically filtered out before entering the graph.
- **Bi-temporal Lineage Graphs**: Represents decisions not as static tags, but as chronological evolutionary chains using `SUPERSEDES`, `REVERSES`, `DEPENDS_ON`, and `CONFLICTS_WITH` relationships.
- **Decision Guard**: Evaluates incoming pull requests or architecture proposals against active and reversed decisions in <50ms, identifying potential regressions and suggesting the original deciders as reviewers.
- **Cross-Session Memory Graph**: Uses dedicated FalkorDB memory graphs (`mem_<user_id>`) to recall past inquiries and pinned insights across engineering sessions.
- **Interactive Visual Canvas**: Cytoscape UI provides real-time graph traversal, tool execution traces, and verified citation chips.
- **FastMCP Protocol**: Standard MCP stdio server exposes all 14 graph tools directly to Claude Desktop, IDEs, and autonomous coding agents.

## 3. How FalkorDB is Used
FalkorDB serves as the ultra-low latency graph engine:
1. **Full-Text Decision Search**: Idempotent full-text indexes (`db.idx.fulltext.createNodeIndex('Decision', 'title', 'summary')`) power sub-millisecond keyword lookup.
2. **Variable-Length Lineage Traversal**: Cypher queries traverse `(d:Decision)-[:SUPERSEDES*1..6]->(prev)` to trace why legacy choices were replaced.
3. **Decay-Weighted Expertise Graphs**: Models `(Person)-[:KNOWS {score}]->(Module)` using recency-decay algorithms over authored PRs and reviews.
4. **Graph Centrality (PageRank)**: Identifies key maintainers across decision subgraphs using NetworkX algorithms over exported FalkorDB connected subgraphs.

## 4. Benchmark Highlights (From eval/REPORT.md)
- **12/12 Canonical Benchmark Questions Passed** (100.0% expected decision retrieval rate).
- **100% Citation Validity** after 1-turn repair verification.
- **20.9 ms Average Query Latency** against real Flask repository graph.

## 5. Repository Links & Quickstart
- **GitHub Repository**: [ADITYASINGH1206/Graph-Hacks](https://github.com/ADITYASINGH1206/Graph-Hacks)
- **Track**: Track 3 (Company Brain)
- **Live Demo Quickstart**:
  ```bash
  docker compose up -d
  ./scripts/demo_reset.sh
  dig serve
  # In another terminal:
  cd frontend && npm run dev
  ```
