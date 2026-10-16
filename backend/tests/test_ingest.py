"""Unit tests for GitHub ingestion, thread normalization, and disk caching."""

import pytest
from dig.ingest.cache import (
    is_cache_fresh,
    load_normalized_threads,
    save_cached_item,
    save_normalized_threads,
)
from dig.ingest.github import GitHubClient
from dig.ingest.normalize import (
    extract_closes_and_references,
    is_bot_user,
    normalize_thread,
)

SAMPLE_RAW_ISSUE = {
    "item": {
        "number": 123,
        "title": "Deprecate legacy session serializer",
        "state": "closed",
        "html_url": "https://github.com/pallets/flask/issues/123",
        "user": {"login": "alice", "type": "User"},
        "created_at": "2021-03-01T10:00:00Z",
        "updated_at": "2021-03-05T12:00:00Z",
        "closed_at": "2021-03-05T12:00:00Z",
        "body": "We should deprecate the old session format. Closes #100 and references #105.",
        "labels": [{"name": "deprecation"}, {"name": "security"}],
    },
    "kind": "issues",
    "comments": [
        {
            "id": 456,
            "user": {"login": "bob", "type": "User"},
            "created_at": "2021-03-02T11:00:00Z",
            "body": "Agreed, let's move to itsdangerous modern serializer.",
            "html_url": "https://github.com/pallets/flask/issues/123#issuecomment-456",
        }
    ],
}

SAMPLE_RAW_PR = {
    "item": {
        "number": 77,
        "pull_request": {"merged_at": "2022-01-10T15:00:00Z"},
        "title": "Remove old JSON encoder",
        "state": "closed",
        "html_url": "https://github.com/pallets/flask/pull/77",
        "user": {"login": "dependabot[bot]", "type": "Bot"},
        "created_at": "2022-01-08T09:00:00Z",
        "updated_at": "2022-01-10T15:00:00Z",
        "body": "Fixes #50. Removes deprecated custom encoder in favor of standard library.",
        "labels": [{"name": "cleanup"}],
    },
    "kind": "pulls",
    "comments": [],
    "reviews": [
        {
            "id": 888,
            "user": {"login": "maintainer_dan", "type": "User"},
            "submitted_at": "2022-01-09T14:00:00Z",
            "body": "Looks good to me, clean removal.",
            "html_url": "https://github.com/pallets/flask/pull/77#pullrequestreview-888",
        }
    ],
    "review_comments": [
        {
            "id": 999,
            "user": {"login": "charlie", "type": "User"},
            "created_at": "2022-01-09T12:00:00Z",
            "body": "Check backward compatibility here.",
            "html_url": "https://github.com/pallets/flask/pull/77#discussion_r999",
        }
    ],
    "files": [{"filename": "src/flask/json.py"}, {"filename": "tests/test_json.py"}],
}


def test_normalize_issue():
    """Verify issue normalization, block formatting, and link extraction."""
    thread = normalize_thread(SAMPLE_RAW_ISSUE)
    assert thread.source_id == "issue:123"
    assert thread.kind == "issue"
    assert thread.number == 123
    assert thread.author == "alice"
    assert not thread.is_author_bot
    assert len(thread.blocks) == 2

    # Check block IDs
    assert thread.blocks[0].id == "issue:123#body"
    assert thread.blocks[0].kind == "issue_body"
    assert thread.blocks[1].id == "issue:123#c456"
    assert thread.blocks[1].kind == "comment"

    # Check closes and references parsing
    assert thread.closes == [100]
    assert thread.references == [105]


def test_normalize_pr_and_bot():
    """Verify PR normalization, review blocks, files, and bot flag."""
    thread = normalize_thread(SAMPLE_RAW_PR)
    assert thread.source_id == "pr:77"
    assert thread.kind == "pr"
    assert thread.is_author_bot is True
    assert thread.files == ["src/flask/json.py", "tests/test_json.py"]
    assert thread.closes == [50]

    block_ids = [b.id for b in thread.blocks]
    assert "pr:77#body" in block_ids
    assert "pr:77#review:888" in block_ids
    assert "pr:77#rc999" in block_ids


def test_is_bot_user():
    """Verify bot user detection rules."""
    assert is_bot_user({"login": "github-actions[bot]", "type": "Bot"})
    assert is_bot_user({"login": "renovate-bot", "type": "User"})
    assert is_bot_user({"login": "pallets_bot", "type": "User"})
    assert not is_bot_user({"login": "davidism", "type": "User"})
    assert not is_bot_user(None)


def test_extract_closes_and_references():
    """Test regex link extraction from issue bodies."""
    text = "This closes #42 and fixes https://github.com/pallets/flask/issues/43. See also #44 and #45."
    closes, refs = extract_closes_and_references(text, current_number=99)
    assert closes == [42, 43]
    assert refs == [44, 45]


def test_disk_cache_and_freshness(tmp_path, monkeypatch):
    """Test cache saving, freshness validation, and loading."""
    monkeypatch.setattr("dig.ingest.cache.BASE_DATA_DIR", tmp_path)

    repo = "test_owner/test_repo"
    save_cached_item(repo, "issues", 123, SAMPLE_RAW_ISSUE)

    # Fresh timestamp
    assert is_cache_fresh(repo, "issues", 123, "2021-03-05T12:00:00Z") is True
    # Stale timestamp
    assert is_cache_fresh(repo, "issues", 123, "2021-03-10T00:00:00Z") is False
    # Non-existent
    assert is_cache_fresh(repo, "issues", 999, "2021-03-05T12:00:00Z") is False

    # Save and load normalized threads
    thread = normalize_thread(SAMPLE_RAW_ISSUE)
    save_normalized_threads(repo, [thread.model_dump()])
    loaded = load_normalized_threads(repo)
    assert len(loaded) == 1
    assert loaded[0]["source_id"] == "issue:123"


@pytest.mark.asyncio
async def test_github_client_uses_cache(tmp_path, monkeypatch):
    """Verify that GitHubClient returns cached data without making network calls."""
    monkeypatch.setattr("dig.ingest.cache.BASE_DATA_DIR", tmp_path)
    repo = "test_owner/test_repo"
    save_cached_item(repo, "issues", 123, SAMPLE_RAW_ISSUE)

    client = GitHubClient(token="fake_token", repo=repo)
    try:
        # Request thread with matching updated_at
        result = await client.ingest_thread_details(
            repo,
            {"number": 123, "updated_at": "2021-03-05T12:00:00Z"},
        )
        assert result["item"]["number"] == 123
        assert client.network_calls_made == 0  # Zero network calls made!
    finally:
        await client.close()
