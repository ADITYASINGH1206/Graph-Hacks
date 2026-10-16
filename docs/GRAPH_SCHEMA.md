# Graph schema (FalkorDB, openCypher)

Graph name: `dig_<owner>_<repo>`. All properties are scalars or arrays of scalars (FalkorDB limitation).

## Nodes
| Label | Key | Properties |
|---|---|---|
| `Person` | `login` | `name`, `avatar_url`, `is_bot` |
| `Issue` | `number` | `title`, `state`, `created_at`, `closed_at`, `updated_at`, `url`, `labels[]`, `extracted_at` |
| `PullRequest` | `number` | `title`, `state`, `merged`, `created_at`, `merged_at`, `updated_at`, `url`, `labels[]`, `extracted_at` |
| `Release` | `tag` | `name`, `published_at`, `url` |
| `File` | `path` | |
| `Module` | `name` | derived from path prefix at `MODULE_DEPTH` |
| `Concept` | `name` | normalised lowercase noun phrase (e.g. `session cookie`) |
| `Evidence` | `id` | `kind` (issue_body/comment/pr_body/review/release_note), `source_id`, `quote` (max 400 chars, verified), `url`, `author`, `ts` |
| `Decision` | `id` | `title`, `summary`, `type`, `status`, `decided_at`, `valid_from`, `valid_to`, `confidence`, `extracted_at` |

Decision `type`: `deprecation | removal | adoption | revert | design | policy | wontfix`.
Decision `status`: `active | superseded | reversed`.
`Decision.id` = `dec_` + first 12 hex of sha1(`source_id` + normalised title).

## Edges
| Edge | From to To | Properties |
|---|---|---|
| `AUTHORED` | Person to Issue, PullRequest, Evidence | |
| `REVIEWED` | Person to PullRequest | `state` |
| `COMMENTED_ON` | Person to Issue, PullRequest | `count` |
| `CLOSES` | PullRequest to Issue | |
| `REFERENCES` | Issue/PullRequest to Issue/PullRequest | |
| `TOUCHES` | PullRequest to File | `additions`, `deletions` |
| `IN_MODULE` | File to Module | |
| `SHIPPED_IN` | PullRequest to Release | |
| `DECIDED_IN` | Decision to Issue, PullRequest, Release | |
| `MADE` | Person to Decision | `role` (proposer/approver/maintainer) |
| `SUPPORTED_BY` | Decision to Evidence | |
| `AFFECTS` | Decision to Module, File, Concept | |
| `SUPERSEDES` | Decision to Decision | `confidence`, `reason` |
| `REVERSES` | Decision to Decision | `confidence`, `reason` |
| `DEPENDS_ON` | Decision to Decision | `confidence` |
| `CONFLICTS_WITH` | Decision to Decision | `confidence`, `reason` |
| `KNOWS` | Person to Module | `score`, `authored`, `reviewed`, `commented`, `last_active` |

## Indexes (verify syntax at docs.falkordb.com)
```cypher
CREATE INDEX FOR (n:Person) ON (n.login)
CREATE INDEX FOR (n:Issue) ON (n.number)
CREATE INDEX FOR (n:PullRequest) ON (n.number)
CREATE INDEX FOR (n:Decision) ON (n.id)
CREATE INDEX FOR (n:Evidence) ON (n.id)
CREATE INDEX FOR (n:Module) ON (n.name)
CREATE INDEX FOR (n:File) ON (n.path)
CREATE INDEX FOR (n:Release) ON (n.tag)
CALL db.idx.fulltext.createNodeIndex('Decision', 'title', 'summary')
```

## Core queries (templates for `graph/queries.py`)

**Search decisions**
```cypher
CALL db.idx.fulltext.queryNodes('Decision', $q) YIELD node, score
OPTIONAL MATCH (node)-[:AFFECTS]->(m:Module)
WITH node, score, collect(DISTINCT m.name) AS modules
WHERE $module IS NULL OR $module IN modules
RETURN node.id AS id, node.title AS title, node.type AS type, node.status AS status,
       node.decided_at AS decided_at, modules, score
ORDER BY score DESC LIMIT $limit
```

**Decision with evidence and people**
```cypher
MATCH (d:Decision {id: $id})
OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(e:Evidence)
OPTIONAL MATCH (p:Person)-[r:MADE]->(d)
OPTIONAL MATCH (d)-[:DECIDED_IN]->(src)
RETURN d, collect(DISTINCT e) AS evidence, collect(DISTINCT {login: p.login, role: r.role}) AS people,
       collect(DISTINCT src.url) AS sources
```

**Lineage (both directions)**
```cypher
MATCH path = (d:Decision {id: $id})-[:SUPERSEDES|REVERSES*1..6]-(o:Decision)
RETURN path
```
Order the result by `decided_at` in Python and label each hop with direction.

**Who knows a module**
```cypher
MATCH (p:Person)-[k:KNOWS]->(m:Module {name: $module})
WHERE p.is_bot = false
RETURN p.login AS login, k.score AS score, k.authored AS authored, k.reviewed AS reviewed,
       k.commented AS commented, k.last_active AS last_active
ORDER BY k.score DESC LIMIT $limit
```

**Impact of a decision**
```cypher
MATCH (d:Decision {id: $id})-[:AFFECTS]->(x)
OPTIONAL MATCH (d)<-[:DEPENDS_ON]-(down:Decision)
OPTIONAL MATCH (d)-[:DECIDED_IN]->(:PullRequest)-[:SHIPPED_IN]->(r:Release)
RETURN collect(DISTINCT {label: labels(x)[0], name: coalesce(x.name, x.path)}) AS affected,
       collect(DISTINCT down.id) AS downstream, collect(DISTINCT r.tag) AS releases
```

**Active decisions for modules (Decision Guard)**
```cypher
MATCH (d:Decision {status: 'active'})-[:AFFECTS]->(m:Module)
WHERE m.name IN $modules
RETURN d.id AS id, d.title AS title, d.type AS type, d.summary AS summary, collect(DISTINCT m.name) AS modules
```

**Shortest path between two entities**
```cypher
MATCH (a {id: $a}), (b {id: $b})
MATCH p = shortestPath((a)-[*..6]-(b))
RETURN p
```
Entities use their key property; add a generic `uid` property (`<label>:<key>`) on every node at load time so lookups by one parameter work across labels.

## Graph algorithms
Target calls: PageRank on Person-Module-Decision subgraph for "most influential person", BFS for neighbourhood expansion, WCC for decision clusters. Confirm exact procedure names in the FalkorDB docs (`algo.*`). If unavailable, export the subgraph with one Cypher query and use networkx in `graph/algos.py`. The tool interface stays identical either way.
