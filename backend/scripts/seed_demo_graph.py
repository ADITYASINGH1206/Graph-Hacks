"""Seed script for Decision Archaeologist demo graph (~40 nodes and edges).

Creates:
- 3 Decisions (with SUPERSEDES relation chain)
- 5 Persons (including 1 bot)
- 3 Modules
- 3 Files
- 3 PullRequests
- 2 Releases
- 3 Evidence items with verified quotes
- KNOWS edges with expertise scores
- AFFECTS, DECIDED_IN, MADE, SUPPORTED_BY, IN_MODULE, SHIPPED_IN edges
"""

from typing import Any

from dig.graph.client import get_graph
from dig.graph.schema import ensure_schema


def seed_demo_graph(
    graph: Any | None = None, graph_name: str = "dig_pallets_flask"
) -> dict[str, int]:
    """Populate graph with realistic mock data for testing and offline demo."""
    if graph is None:
        graph = get_graph(graph_name)

    # Ensure schema and indexes exist
    ensure_schema(graph)

    # Clear existing graph data for idempotent seed
    graph.query("MATCH (n) DETACH DELETE n")

    cypher_statements = [
        # 1. Modules
        """
        CREATE (m1:Module {name: 'flask/app', uid: 'Module:flask/app'})
        CREATE (m2:Module {name: 'flask/compat', uid: 'Module:flask/compat'})
        CREATE (m3:Module {name: 'flask/views', uid: 'Module:flask/views'})
        """,
        # 2. Files
        """
        CREATE (f1:File {path: 'src/flask/app.py', uid: 'File:src/flask/app.py'})
        CREATE (f2:File {path: 'src/flask/compat.py', uid: 'File:src/flask/compat.py'})
        CREATE (f3:File {path: 'src/flask/views.py', uid: 'File:src/flask/views.py'})
        """,
        # 3. Persons
        """
        CREATE (p1:Person {login: 'davidism', name: 'David Lord', avatar_url: 'https://avatars.githubusercontent.com/u/12428', is_bot: false, uid: 'Person:davidism'})
        CREATE (p2:Person {login: 'mitsuhiko', name: 'Armin Ronacher', avatar_url: 'https://avatars.githubusercontent.com/u/7396', is_bot: false, uid: 'Person:mitsuhiko'})
        CREATE (p3:Person {login: 'untitaker', name: 'Markus Unterwaditzer', avatar_url: 'https://avatars.githubusercontent.com/u/837573', is_bot: false, uid: 'Person:untitaker'})
        CREATE (p4:Person {login: 'pgjones', name: 'Philip Jones', avatar_url: 'https://avatars.githubusercontent.com/u/5144670', is_bot: false, uid: 'Person:pgjones'})
        CREATE (p5:Person {login: 'pallets-bot', name: 'Pallets Automation', avatar_url: 'https://avatars.githubusercontent.com/u/9999999', is_bot: true, uid: 'Person:pallets-bot'})
        """,
        # 4. Releases
        """
        CREATE (r1:Release {tag: '2.0.0', name: 'Flask 2.0.0', published_at: '2021-05-11T12:00:00Z', url: 'https://github.com/pallets/flask/releases/tag/2.0.0', uid: 'Release:2.0.0'})
        CREATE (r2:Release {tag: '2.2.0', name: 'Flask 2.2.0', published_at: '2022-08-01T15:30:00Z', url: 'https://github.com/pallets/flask/releases/tag/2.2.0', uid: 'Release:2.2.0'})
        """,
        # 5. Pull Requests
        """
        CREATE (pr1:PullRequest {number: 3500, title: 'Drop support for Python 2 and 3.5', state: 'closed', merged: true, created_at: '2020-05-10T10:00:00Z', merged_at: '2020-05-15T18:00:00Z', updated_at: '2020-05-15T18:00:00Z', url: 'https://github.com/pallets/flask/pull/3500', labels: ['breaking', 'python2'], uid: 'PullRequest:3500'})
        CREATE (pr2:PullRequest {number: 3900, title: 'Async view and error handler support', state: 'closed', merged: true, created_at: '2020-12-01T14:00:00Z', merged_at: '2021-01-10T20:00:00Z', updated_at: '2021-01-10T20:00:00Z', url: 'https://github.com/pallets/flask/pull/3900', labels: ['async', 'feature'], uid: 'PullRequest:3900'})
        CREATE (pr3:PullRequest {number: 4400, title: 'Drop support for Python 3.6', state: 'closed', merged: true, created_at: '2022-03-15T09:00:00Z', merged_at: '2022-03-20T16:00:00Z', updated_at: '2022-03-20T16:00:00Z', url: 'https://github.com/pallets/flask/pull/4400', labels: ['breaking', 'python36'], uid: 'PullRequest:4400'})
        """,
        # 6. Evidence
        """
        CREATE (e1:Evidence {id: 'ev_drop_py2', kind: 'pr_body', source_id: 'pr:3500#body', quote: 'Python 2 has reached end of life, dropping Python 2 compatibility code across the codebase.', url: 'https://github.com/pallets/flask/pull/3500', author: 'davidism', ts: '2020-05-10T10:00:00Z', uid: 'Evidence:ev_drop_py2'})
        CREATE (e2:Evidence {id: 'ev_drop_py36', kind: 'pr_body', source_id: 'pr:4400#body', quote: 'Python 3.6 and 3.7 are now EOL, bump minimum Python version to 3.8.', url: 'https://github.com/pallets/flask/pull/4400', author: 'davidism', ts: '2022-03-15T09:00:00Z', uid: 'Evidence:ev_drop_py36'})
        CREATE (e3:Evidence {id: 'ev_async_views', kind: 'comment', source_id: 'pr:3900#c123', quote: 'Add support for async route handlers and views using asgiref.', url: 'https://github.com/pallets/flask/pull/3900#issuecomment-123', author: 'pgjones', ts: '2020-12-05T11:20:00Z', uid: 'Evidence:ev_async_views'})
        """,
        # 7. Decisions
        """
        CREATE (d1:Decision {id: 'dec_drop_py2', title: 'Drop Python 2 support', summary: 'Dropped Python 2 and 3.5 support in Flask 2.0 to modernize codebase.', type: 'deprecation', status: 'superseded', decided_at: '2020-05-15T18:00:00Z', valid_from: '2020-05-15T18:00:00Z', valid_to: '2022-03-20T16:00:00Z', confidence: 0.95, extracted_at: '2026-10-16T00:00:00Z', uid: 'Decision:dec_drop_py2'})
        CREATE (d2:Decision {id: 'dec_drop_py36', title: 'Drop Python 3.6 support', summary: 'Dropped Python 3.6 and 3.7 support, requiring Python 3.8+.', type: 'deprecation', status: 'active', decided_at: '2022-03-20T16:00:00Z', valid_from: '2022-03-20T16:00:00Z', valid_to: null, confidence: 0.98, extracted_at: '2026-10-16T00:00:00Z', uid: 'Decision:dec_drop_py36'})
        CREATE (d3:Decision {id: 'dec_async_views', title: 'Adopt async views and route handlers', summary: 'Added first-class async route and view support using asgiref in Flask 2.0.', type: 'adoption', status: 'active', decided_at: '2021-01-10T20:00:00Z', valid_from: '2021-01-10T20:00:00Z', valid_to: null, confidence: 0.92, extracted_at: '2026-10-16T00:00:00Z', uid: 'Decision:dec_async_views'})
        """,
        # 8. Structural Edges: IN_MODULE, SHIPPED_IN, TOUCHES
        """
        MATCH (f1:File {path: 'src/flask/app.py'}), (m1:Module {name: 'flask/app'}) CREATE (f1)-[:IN_MODULE]->(m1)
        """,
        """
        MATCH (f2:File {path: 'src/flask/compat.py'}), (m2:Module {name: 'flask/compat'}) CREATE (f2)-[:IN_MODULE]->(m2)
        """,
        """
        MATCH (f3:File {path: 'src/flask/views.py'}), (m3:Module {name: 'flask/views'}) CREATE (f3)-[:IN_MODULE]->(m3)
        """,
        """
        MATCH (pr1:PullRequest {number: 3500}), (r1:Release {tag: '2.0.0'}) CREATE (pr1)-[:SHIPPED_IN]->(r1)
        """,
        """
        MATCH (pr2:PullRequest {number: 3900}), (r1:Release {tag: '2.0.0'}) CREATE (pr2)-[:SHIPPED_IN]->(r1)
        """,
        """
        MATCH (pr3:PullRequest {number: 4400}), (r2:Release {tag: '2.2.0'}) CREATE (pr3)-[:SHIPPED_IN]->(r2)
        """,
        """
        MATCH (pr1:PullRequest {number: 3500}), (f2:File {path: 'src/flask/compat.py'}) CREATE (pr1)-[:TOUCHES {additions: 10, deletions: 120}]->(f2)
        """,
        """
        MATCH (pr2:PullRequest {number: 3900}), (f3:File {path: 'src/flask/views.py'}) CREATE (pr2)-[:TOUCHES {additions: 85, deletions: 5}]->(f3)
        """,
        """
        MATCH (p1:Person {login: 'davidism'}), (pr1:PullRequest {number: 3500}) CREATE (p1)-[:AUTHORED]->(pr1)
        """,
        """
        MATCH (p4:Person {login: 'pgjones'}), (pr2:PullRequest {number: 3900}) CREATE (p4)-[:AUTHORED]->(pr2)
        """,
        """
        MATCH (p1:Person {login: 'davidism'}), (pr3:PullRequest {number: 4400}) CREATE (p1)-[:AUTHORED]->(pr3)
        """,
        # 9. Decision Connections: SUPPORTED_BY, MADE, DECIDED_IN, AFFECTS, SUPERSEDES
        """
        MATCH (d1:Decision {id: 'dec_drop_py2'}), (e1:Evidence {id: 'ev_drop_py2'}) CREATE (d1)-[:SUPPORTED_BY]->(e1)
        """,
        """
        MATCH (d2:Decision {id: 'dec_drop_py36'}), (e2:Evidence {id: 'ev_drop_py36'}) CREATE (d2)-[:SUPPORTED_BY]->(e2)
        """,
        """
        MATCH (d3:Decision {id: 'dec_async_views'}), (e3:Evidence {id: 'ev_async_views'}) CREATE (d3)-[:SUPPORTED_BY]->(e3)
        """,
        """
        MATCH (p1:Person {login: 'davidism'}), (d1:Decision {id: 'dec_drop_py2'}) CREATE (p1)-[:MADE {role: 'maintainer'}]->(d1)
        """,
        """
        MATCH (p1:Person {login: 'davidism'}), (d2:Decision {id: 'dec_drop_py36'}) CREATE (p1)-[:MADE {role: 'maintainer'}]->(d2)
        """,
        """
        MATCH (p4:Person {login: 'pgjones'}), (d3:Decision {id: 'dec_async_views'}) CREATE (p4)-[:MADE {role: 'proposer'}]->(d3)
        """,
        """
        MATCH (p1:Person {login: 'davidism'}), (d3:Decision {id: 'dec_async_views'}) CREATE (p1)-[:MADE {role: 'approver'}]->(d3)
        """,
        """
        MATCH (d1:Decision {id: 'dec_drop_py2'}), (pr1:PullRequest {number: 3500}) CREATE (d1)-[:DECIDED_IN]->(pr1)
        """,
        """
        MATCH (d2:Decision {id: 'dec_drop_py36'}), (pr3:PullRequest {number: 4400}) CREATE (d2)-[:DECIDED_IN]->(pr3)
        """,
        """
        MATCH (d3:Decision {id: 'dec_async_views'}), (pr2:PullRequest {number: 3900}) CREATE (d3)-[:DECIDED_IN]->(pr2)
        """,
        """
        MATCH (d1:Decision {id: 'dec_drop_py2'}), (m2:Module {name: 'flask/compat'}) CREATE (d1)-[:AFFECTS]->(m2)
        """,
        """
        MATCH (d2:Decision {id: 'dec_drop_py36'}), (m2:Module {name: 'flask/compat'}) CREATE (d2)-[:AFFECTS]->(m2)
        """,
        """
        MATCH (d2:Decision {id: 'dec_drop_py36'}), (m1:Module {name: 'flask/app'}) CREATE (d2)-[:AFFECTS]->(m1)
        """,
        """
        MATCH (d3:Decision {id: 'dec_async_views'}), (m3:Module {name: 'flask/views'}) CREATE (d3)-[:AFFECTS]->(m3)
        """,
        """
        MATCH (d3:Decision {id: 'dec_async_views'}), (m1:Module {name: 'flask/app'}) CREATE (d3)-[:AFFECTS]->(m1)
        """,
        # Lineage: d2 SUPERSEDES d1
        """
        MATCH (d2:Decision {id: 'dec_drop_py36'}), (d1:Decision {id: 'dec_drop_py2'})
        CREATE (d2)-[:SUPERSEDES {confidence: 0.9, reason: 'Python 3.6+ deprecation supersedes Python 2 deprecation'}]->(d1)
        """,
        # 10. Expertise: KNOWS edges
        """
        MATCH (p1:Person {login: 'davidism'}), (m1:Module {name: 'flask/app'})
        CREATE (p1)-[:KNOWS {score: 9.5, authored: 25, reviewed: 40, commented: 60, last_active: '2024-01-15'}]->(m1)
        """,
        """
        MATCH (p1:Person {login: 'davidism'}), (m2:Module {name: 'flask/compat'})
        CREATE (p1)-[:KNOWS {score: 7.2, authored: 8, reviewed: 12, commented: 20, last_active: '2023-09-01'}]->(m2)
        """,
        """
        MATCH (p4:Person {login: 'pgjones'}), (m3:Module {name: 'flask/views'})
        CREATE (p4)-[:KNOWS {score: 8.8, authored: 12, reviewed: 15, commented: 25, last_active: '2023-11-20'}]->(m3)
        """,
        """
        MATCH (p2:Person {login: 'mitsuhiko'}), (m1:Module {name: 'flask/app'})
        CREATE (p2)-[:KNOWS {score: 5.0, authored: 50, reviewed: 5, commented: 10, last_active: '2019-06-01'}]->(m1)
        """,
        """
        MATCH (p3:Person {login: 'untitaker'}), (m2:Module {name: 'flask/compat'})
        CREATE (p3)-[:KNOWS {score: 4.5, authored: 6, reviewed: 8, commented: 14, last_active: '2021-04-10'}]->(m2)
        """,
    ]

    for stmt in cypher_statements:
        graph.query(stmt)

    # Return total counts
    nodes_res = graph.query("MATCH (n) RETURN count(n) AS cnt")
    edges_res = graph.query("MATCH ()-[r]->() RETURN count(r) AS cnt")
    node_count = int(nodes_res.result_set[0][0]) if nodes_res.result_set else 0
    edge_count = int(edges_res.result_set[0][0]) if edges_res.result_set else 0

    return {"nodes": node_count, "edges": edge_count}


if __name__ == "__main__":
    res = seed_demo_graph()
    print(f"Seeded demo graph: {res['nodes']} nodes, {res['edges']} edges.")
