"""Graph loader: bulk ingests structural GitHub entities and edges into FalkorDB using UNWIND batches."""

import json
import logging
import re
from typing import Any

from dig.config import settings
from dig.graph.client import get_graph
from dig.graph.schema import ensure_schema, make_uid
from dig.ingest.cache import BASE_DATA_DIR, load_normalized_threads

logger = logging.getLogger(__name__)


def derive_module(file_path: str, depth: int = 2) -> str:
    """Derive module name from file path prefix up to depth components."""
    clean = file_path.replace("\\", "/").strip("/")
    parts = [p for p in clean.split("/") if p]
    if parts and parts[0] in ("src", "lib"):
        parts = parts[1:]
    if not parts:
        return "root"
    if len(parts) == 1:
        # e.g. "setup.py" -> "setup"
        return parts[0].split(".")[0]
    # For file at end, take directory prefix or filename without extension
    module_parts = parts[:depth]
    # Strip extension from the last part if it has one
    if "." in module_parts[-1]:
        module_parts[-1] = module_parts[-1].split(".")[0]
    return "/".join(module_parts)


def load_cached_releases(repo: str) -> list[dict[str, Any]]:
    """Load cached release JSON files from data/raw/{repo_slug}/releases/."""
    slug = repo.replace("/", "_").replace("-", "_").lower()
    rel_dir = BASE_DATA_DIR / "raw" / slug / "releases"
    if not rel_dir.exists():
        return []

    releases: list[dict[str, Any]] = []
    for file_path in rel_dir.glob("*.json"):
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    releases.append(data)
        except Exception as exc:
            logger.debug("Failed reading release file %s: %s", file_path, exc)

    # Sort releases chronologically by published_at
    releases.sort(key=lambda r: r.get("published_at") or "")
    return releases


def match_release_for_pr(
    pr_number: int,
    merged_at: str | None,
    releases: list[dict[str, Any]],
) -> str | None:
    """Match a merged PR to its release: by explicit citation in release notes or chronological order."""
    if not merged_at:
        return None

    pr_ref_pattern = re.compile(rf"#\b{pr_number}\b")

    # 1. Check if release body or title explicitly cites #pr_number
    for rel in releases:
        body = rel.get("body") or ""
        name = rel.get("name") or ""
        if pr_ref_pattern.search(body) or pr_ref_pattern.search(name):
            return str(rel.get("tag_name") or rel.get("tag") or rel.get("id"))

    # 2. First release published after merged_at
    for rel in releases:
        pub = rel.get("published_at")
        if pub and pub >= merged_at:
            return str(rel.get("tag_name") or rel.get("tag") or rel.get("id"))

    return None


def chunk_list(items: list[Any], chunk_size: int = 500) -> list[list[Any]]:
    """Split a list into chunks of chunk_size."""
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def load_structure(
    graph: Any | None = None,
    repo: str | None = None,
    batch_size: int = 500,
) -> dict[str, Any]:
    """Load all structural nodes and edges from normalized threads into FalkorDB.

    Idempotent: Uses UNWIND batches with MERGE.
    """
    target_repo = repo or settings.target_repo
    if graph is None:
        graph = get_graph()

    # Ensure schema indexes exist
    ensure_schema(graph)

    # Load normalized threads
    threads = load_normalized_threads(target_repo)
    if not threads:
        logger.warning("No normalized threads found for %s. Run dig ingest first.", target_repo)
        return {"loaded": 0, "error": "No threads found"}

    releases = load_cached_releases(target_repo)
    logger.info(
        "Loading structure for %s: %s threads, %s releases...",
        target_repo,
        len(threads),
        len(releases),
    )

    # Containers for deduplicated entities
    persons: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    pull_requests: list[dict[str, Any]] = []
    files_map: dict[str, dict[str, Any]] = {}
    modules_map: dict[str, dict[str, Any]] = {}
    release_nodes: list[dict[str, Any]] = []

    # Containers for edges
    in_module_edges: set[tuple[str, str]] = set()
    authored_issue_edges: set[tuple[str, int]] = set()
    authored_pr_edges: set[tuple[str, int]] = set()
    reviewed_edges: set[tuple[str, int, str]] = set()
    commented_issue_edges: dict[tuple[str, int], int] = {}
    commented_pr_edges: dict[tuple[str, int], int] = {}
    touches_edges: set[tuple[int, str]] = set()
    closes_edges: set[tuple[int, int]] = set()
    shipped_in_edges: set[tuple[int, str]] = set()

    # Process releases
    for rel in releases:
        tag = str(rel.get("tag_name") or rel.get("tag") or rel.get("id"))
        release_nodes.append(
            {
                "tag": tag,
                "uid": make_uid("Release", tag),
                "name": str(rel.get("name") or tag),
                "published_at": rel.get("published_at"),
                "url": rel.get("html_url") or "",
            }
        )

    # Process threads
    for t in threads:
        author = t.get("author") or "ghost"
        is_bot = bool(t.get("is_author_bot", False))
        if author not in persons:
            persons[author] = {
                "login": author,
                "uid": make_uid("Person", author),
                "is_bot": is_bot,
            }

        num = int(t["number"])
        kind = t["kind"]

        if kind == "pr":
            pull_requests.append(
                {
                    "number": num,
                    "uid": make_uid("PullRequest", num),
                    "title": t.get("title", ""),
                    "state": t.get("state", ""),
                    "merged": bool(t.get("merged_at")),
                    "created_at": t.get("created_at"),
                    "merged_at": t.get("merged_at"),
                    "updated_at": t.get("updated_at"),
                    "url": t.get("url", ""),
                    "labels": t.get("labels", []),
                }
            )
            authored_pr_edges.add((author, num))

            # Match release
            rel_tag = match_release_for_pr(num, t.get("merged_at"), releases)
            if rel_tag:
                shipped_in_edges.add((num, rel_tag))

            # Touches & In_Module
            for file_path in t.get("files", []):
                mod_name = derive_module(file_path, depth=settings.module_depth)
                if file_path not in files_map:
                    files_map[file_path] = {"path": file_path, "uid": make_uid("File", file_path)}
                if mod_name not in modules_map:
                    modules_map[mod_name] = {"name": mod_name, "uid": make_uid("Module", mod_name)}
                in_module_edges.add((file_path, mod_name))
                touches_edges.add((num, file_path))

            # Closes
            for closed_num in t.get("closes", []):
                closes_edges.add((num, closed_num))
        else:
            issues.append(
                {
                    "number": num,
                    "uid": make_uid("Issue", num),
                    "title": t.get("title", ""),
                    "state": t.get("state", ""),
                    "created_at": t.get("created_at"),
                    "closed_at": t.get("closed_at"),
                    "updated_at": t.get("updated_at"),
                    "url": t.get("url", ""),
                    "labels": t.get("labels", []),
                }
            )
            authored_issue_edges.add((author, num))

        # Process blocks for comments & reviews
        for b in t.get("blocks", []):
            b_author = b.get("author") or "ghost"
            if b_author not in persons:
                persons[b_author] = {
                    "login": b_author,
                    "uid": make_uid("Person", b_author),
                    "is_bot": False,
                }

            b_kind = b.get("kind")
            if b_kind == "comment":
                if kind == "pr":
                    key = (b_author, num)
                    commented_pr_edges[key] = commented_pr_edges.get(key, 0) + 1
                else:
                    key = (b_author, num)
                    commented_issue_edges[key] = commented_issue_edges.get(key, 0) + 1
            elif b_kind in ("review", "review_comment"):
                reviewed_edges.add((b_author, num, "APPROVED"))

    # Execute Batch UNWIND Queries
    logger.info("Writing nodes to FalkorDB...")

    # 1. Person nodes
    person_list = list(persons.values())
    for chunk in chunk_list(person_list, batch_size):
        cypher = """
        UNWIND $batch AS row
        MERGE (p:Person {login: row.login})
        SET p.uid = row.uid, p.is_bot = row.is_bot
        """
        graph.query(cypher, params={"batch": chunk})

    # 2. Release nodes
    for chunk in chunk_list(release_nodes, batch_size):
        cypher = """
        UNWIND $batch AS row
        MERGE (r:Release {tag: row.tag})
        SET r.uid = row.uid, r.name = row.name, r.published_at = row.published_at, r.url = row.url
        """
        graph.query(cypher, params={"batch": chunk})

    # 3. Module nodes
    module_list = list(modules_map.values())
    for chunk in chunk_list(module_list, batch_size):
        cypher = """
        UNWIND $batch AS row
        MERGE (m:Module {name: row.name})
        SET m.uid = row.uid
        """
        graph.query(cypher, params={"batch": chunk})

    # 4. File nodes
    file_list = list(files_map.values())
    for chunk in chunk_list(file_list, batch_size):
        cypher = """
        UNWIND $batch AS row
        MERGE (f:File {path: row.path})
        SET f.uid = row.uid
        """
        graph.query(cypher, params={"batch": chunk})

    # 5. Issue nodes
    for chunk in chunk_list(issues, batch_size):
        cypher = """
        UNWIND $batch AS row
        MERGE (i:Issue {number: row.number})
        SET i.uid = row.uid, i.title = row.title, i.state = row.state,
            i.created_at = row.created_at, i.closed_at = row.closed_at,
            i.updated_at = row.updated_at, i.url = row.url, i.labels = row.labels
        """
        graph.query(cypher, params={"batch": chunk})

    # 6. PullRequest nodes
    for chunk in chunk_list(pull_requests, batch_size):
        cypher = """
        UNWIND $batch AS row
        MERGE (pr:PullRequest {number: row.number})
        SET pr.uid = row.uid, pr.title = row.title, pr.state = row.state,
            pr.merged = row.merged, pr.created_at = row.created_at,
            pr.merged_at = row.merged_at, pr.updated_at = row.updated_at,
            pr.url = row.url, pr.labels = row.labels
        """
        graph.query(cypher, params={"batch": chunk})

    logger.info("Writing edges to FalkorDB...")

    # 7. IN_MODULE edges
    in_mod_data = [{"path": p, "name": m} for p, m in in_module_edges]
    for chunk in chunk_list(in_mod_data, batch_size):
        cypher = """
        UNWIND $batch AS row
        MATCH (f:File {path: row.path}), (m:Module {name: row.name})
        MERGE (f)-[:IN_MODULE]->(m)
        """
        graph.query(cypher, params={"batch": chunk})

    # 8. AUTHORED Issue edges
    auth_issue_data = [{"login": a, "number": n} for a, n in authored_issue_edges]
    for chunk in chunk_list(auth_issue_data, batch_size):
        cypher = """
        UNWIND $batch AS row
        MATCH (p:Person {login: row.login}), (i:Issue {number: row.number})
        MERGE (p)-[:AUTHORED]->(i)
        """
        graph.query(cypher, params={"batch": chunk})

    # 9. AUTHORED PR edges
    auth_pr_data = [{"login": a, "number": n} for a, n in authored_pr_edges]
    for chunk in chunk_list(auth_pr_data, batch_size):
        cypher = """
        UNWIND $batch AS row
        MATCH (p:Person {login: row.login}), (pr:PullRequest {number: row.number})
        MERGE (p)-[:AUTHORED]->(pr)
        """
        graph.query(cypher, params={"batch": chunk})

    # 10. REVIEWED edges
    rev_data = [{"login": a, "number": n, "state": s} for a, n, s in reviewed_edges]
    for chunk in chunk_list(rev_data, batch_size):
        cypher = """
        UNWIND $batch AS row
        MATCH (p:Person {login: row.login}), (pr:PullRequest {number: row.number})
        MERGE (p)-[r:REVIEWED]->(pr)
        SET r.state = row.state
        """
        graph.query(cypher, params={"batch": chunk})

    # 11. COMMENTED_ON Issue edges
    comm_issue_data = [
        {"login": k[0], "number": k[1], "count": cnt} for k, cnt in commented_issue_edges.items()
    ]
    for chunk in chunk_list(comm_issue_data, batch_size):
        cypher = """
        UNWIND $batch AS row
        MATCH (p:Person {login: row.login}), (i:Issue {number: row.number})
        MERGE (p)-[r:COMMENTED_ON]->(i)
        SET r.count = row.count
        """
        graph.query(cypher, params={"batch": chunk})

    # 12. COMMENTED_ON PR edges
    comm_pr_data = [
        {"login": k[0], "number": k[1], "count": cnt} for k, cnt in commented_pr_edges.items()
    ]
    for chunk in chunk_list(comm_pr_data, batch_size):
        cypher = """
        UNWIND $batch AS row
        MATCH (p:Person {login: row.login}), (pr:PullRequest {number: row.number})
        MERGE (p)-[r:COMMENTED_ON]->(pr)
        SET r.count = row.count
        """
        graph.query(cypher, params={"batch": chunk})

    # 13. TOUCHES edges
    touches_data = [{"number": n, "path": p} for n, p in touches_edges]
    for chunk in chunk_list(touches_data, batch_size):
        cypher = """
        UNWIND $batch AS row
        MATCH (pr:PullRequest {number: row.number}), (f:File {path: row.path})
        MERGE (pr)-[:TOUCHES]->(f)
        """
        graph.query(cypher, params={"batch": chunk})

    # 14. CLOSES edges
    closes_data = [{"pr": pr, "issue": iss} for pr, iss in closes_edges]
    for chunk in chunk_list(closes_data, batch_size):
        cypher = """
        UNWIND $batch AS row
        MATCH (pr:PullRequest {number: row.pr}), (i:Issue {number: row.issue})
        MERGE (pr)-[:CLOSES]->(i)
        """
        graph.query(cypher, params={"batch": chunk})

    # 15. SHIPPED_IN edges
    shipped_data = [{"number": n, "tag": t} for n, t in shipped_in_edges]
    for chunk in chunk_list(shipped_data, batch_size):
        cypher = """
        UNWIND $batch AS row
        MATCH (pr:PullRequest {number: row.number}), (r:Release {tag: row.tag})
        MERGE (pr)-[:SHIPPED_IN]->(r)
        """
        graph.query(cypher, params={"batch": chunk})

    # Query counts per label and edge type
    label_counts: dict[str, int] = {}
    for lbl in ["Person", "Issue", "PullRequest", "Release", "File", "Module"]:
        res = graph.query(f"MATCH (n:{lbl}) RETURN count(n) AS cnt")
        label_counts[lbl] = int(res.result_set[0][0]) if res.result_set else 0

    edge_counts: dict[str, int] = {}
    for rel_type in [
        "IN_MODULE",
        "AUTHORED",
        "REVIEWED",
        "COMMENTED_ON",
        "TOUCHES",
        "CLOSES",
        "SHIPPED_IN",
    ]:
        res = graph.query(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt")
        edge_counts[rel_type] = int(res.result_set[0][0]) if res.result_set else 0

    total_nodes = sum(label_counts.values())
    total_edges = sum(edge_counts.values())

    logger.info(
        "Load complete! Total nodes: %s, Total edges: %s",
        total_nodes,
        total_edges,
    )

    return {
        "nodes": total_nodes,
        "edges": total_edges,
        "labels": label_counts,
        "edge_types": edge_counts,
    }
