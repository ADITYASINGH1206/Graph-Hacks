"""Unit tests for graph structure loader and release matching."""

from dig.graph.client import get_graph
from dig.graph.loader import derive_module, load_structure, match_release_for_pr


def test_derive_module():
    """Verify module derivation from file paths at depth."""
    assert derive_module("src/flask/app.py", depth=2) == "flask/app"
    assert derive_module("src/flask/sansio/app.py", depth=2) == "flask/sansio"
    assert derive_module("tests/test_basic.py", depth=2) == "tests/test_basic"
    assert derive_module("setup.py", depth=2) == "setup"
    assert derive_module(".github/workflows/tests.yaml", depth=2) == ".github/workflows"


def test_match_release_for_pr():
    """Verify release matching by citation and by merge date."""
    releases = [
        {"tag": "1.0.0", "published_at": "2020-01-01T00:00:00Z", "body": "Release 1.0.0"},
        {
            "tag": "2.0.0",
            "published_at": "2021-05-01T00:00:00Z",
            "body": "Includes #3900 async views",
        },
        {"tag": "2.1.0", "published_at": "2022-01-01T00:00:00Z", "body": "Maintenance release"},
    ]

    # Explicit citation in release body
    tag1 = match_release_for_pr(3900, "2020-05-01T00:00:00Z", releases)
    assert tag1 == "2.0.0"

    # Chronological match (merged between 1.0.0 and 2.0.0, without citation)
    tag2 = match_release_for_pr(3500, "2020-06-01T00:00:00Z", releases)
    assert tag2 == "2.0.0"

    # PR not merged
    assert match_release_for_pr(9999, None, releases) is None


def test_load_structure_idempotency(tmp_path, monkeypatch):
    """Verify load_structure runs idempotently and populates FalkorDB."""
    test_graph = get_graph("dig_test_loader")
    # Clean test graph
    test_graph.query("MATCH (n) DETACH DELETE n")

    # Seed 2 mock threads in memory or test
    mock_threads = [
        {
            "source_id": "pr:101",
            "kind": "pr",
            "number": 101,
            "title": "Add test feature",
            "state": "closed",
            "author": "tester_bob",
            "is_author_bot": False,
            "created_at": "2022-01-01T10:00:00Z",
            "merged_at": "2022-01-02T10:00:00Z",
            "updated_at": "2022-01-02T10:00:00Z",
            "url": "https://github.com/test/repo/pull/101",
            "labels": ["feature"],
            "files": ["src/flask/app.py"],
            "blocks": [],
            "closes": [50],
        },
        {
            "source_id": "issue:50",
            "kind": "issue",
            "number": 50,
            "title": "Bug in app",
            "state": "closed",
            "author": "alice",
            "is_author_bot": False,
            "created_at": "2021-12-01T10:00:00Z",
            "updated_at": "2022-01-02T10:00:00Z",
            "url": "https://github.com/test/repo/issues/50",
            "labels": ["bug"],
            "blocks": [],
            "files": [],
        },
    ]

    monkeypatch.setattr(
        "dig.graph.loader.load_normalized_threads",
        lambda repo: mock_threads,
    )
    monkeypatch.setattr(
        "dig.graph.loader.load_cached_releases",
        lambda repo: [{"tag": "1.0", "published_at": "2022-02-01T00:00:00Z", "name": "1.0"}],
    )

    # First load
    res1 = load_structure(graph=test_graph, repo="test/repo")
    nodes1 = res1["nodes"]
    edges1 = res1["edges"]
    assert nodes1 >= 5  # Person, PR, Issue, File, Module, Release
    assert edges1 >= 4  # AUTHORED, IN_MODULE, TOUCHES, CLOSES, SHIPPED_IN

    # Second load should produce identical count
    res2 = load_structure(graph=test_graph, repo="test/repo")
    assert res2["nodes"] == nodes1
    assert res2["edges"] == edges1
