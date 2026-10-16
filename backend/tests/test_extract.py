"""Unit tests for decision signals, extraction prompt formatting, and evidence verification."""

from dig.extract.extractor import generate_decision_id
from dig.extract.prompts import format_thread_for_llm
from dig.extract.signals import filter_threads, score_thread
from dig.extract.verify import (
    verify_evidence_quote,
    verify_extracted_decision,
)


def test_signal_scoring():
    """Verify scoring logic for labels, keywords, PR reviews, and comments."""
    # Label matching
    t_label = {"labels": ["deprecation", "bug"], "blocks": []}
    assert score_thread(t_label) >= 3

    # Keyword matching in title
    t_title = {"title": "Drop support for Python 2", "labels": [], "blocks": []}
    assert score_thread(t_title) >= 2

    # PR with 5+ files
    t_pr = {
        "kind": "pr",
        "merged_at": "2022-01-01T00:00:00Z",
        "files": ["f1", "f2", "f3", "f4", "f5"],
        "labels": [],
        "blocks": [],
    }
    assert score_thread(t_pr) >= 2

    # Thread with 6+ comments
    t_comments = {
        "labels": [],
        "blocks": [{"kind": "comment"} for _ in range(7)],
    }
    assert score_thread(t_comments) >= 1


def test_filter_threads():
    """Verify threshold filtering and sorting."""
    threads = [
        {"title": "Bug", "labels": [], "blocks": []},  # 0
        {"title": "Deprecate old serializer", "labels": [], "blocks": []},  # 2
        {"title": "Drop support for 3.6", "labels": ["breaking"], "blocks": []},  # 5
    ]
    filtered = filter_threads(threads, threshold=2)
    assert len(filtered) == 2
    assert filtered[0][1] >= filtered[1][1]


def test_verify_exact_match():
    """Verify exact substring matches pass verification."""
    block = "We decided to deprecate custom session handlers in Flask 2.0."
    quote = "deprecate custom session handlers in Flask 2.0."
    assert verify_evidence_quote(quote, block) is True


def test_verify_curly_quotes_and_whitespace():
    """Verify curly quotes and whitespace normalization pass verification."""
    block = "Armin said: “We won’t support Python 2   any longer.”"
    quote = "We won't support Python 2 any longer."
    assert verify_evidence_quote(quote, block) is True


def test_verify_hallucinated_quote_rejected():
    """Verify hallucinated quote not present in block is rejected, and decision is dropped."""
    blocks_by_id = {
        "issue:100#body": "This issue is about improving performance of template rendering."
    }

    hallucinated_decision = {
        "title": "Drop template rendering",
        "summary": "Decided to abandon Jinja2 templates.",
        "type": "deprecation",
        "status_hint": "active",
        "evidence": [
            {
                "block_id": "issue:100#body",
                "quote": "We will abandon Jinja2 entirely and use raw HTML strings.",
            }
        ],
    }

    verified, kept, dropped = verify_extracted_decision(hallucinated_decision, blocks_by_id)
    assert verified is None  # Dropped because no evidence was verified!
    assert kept == 0
    assert dropped == 1


def test_verify_partial_evidence_kept():
    """Verify decision with 1 valid and 1 invalid quote keeps only the valid quote."""
    blocks_by_id = {
        "pr:200#body": "We decided to use asgiref for async view support.",
        "pr:200#c1": "Thanks for the pull request.",
    }

    decision = {
        "title": "Use asgiref for async views",
        "summary": "Adopted asgiref.",
        "type": "adoption",
        "status_hint": "active",
        "evidence": [
            {"block_id": "pr:200#body", "quote": "use asgiref for async view support."},
            {"block_id": "pr:200#c1", "quote": "this quote is completely made up by model"},
        ],
    }

    verified, kept, dropped = verify_extracted_decision(decision, blocks_by_id)
    assert verified is not None
    assert kept == 1
    assert dropped == 1
    assert len(verified["evidence"]) == 1
    assert verified["evidence"][0]["quote"] == "use asgiref for async view support."


def test_generate_decision_id():
    """Verify deterministic decision ID formatting."""
    id1 = generate_decision_id("pr:3900", "Adopt async views")
    id2 = generate_decision_id("pr:3900", "Adopt   Async  Views")
    assert id1.startswith("dec_")
    assert len(id1) == 16  # "dec_" + 12 chars
    assert id1 == id2  # Case & whitespace normalized


def test_format_thread_for_llm_truncation():
    """Verify thread formatting and length budget."""
    thread = {
        "source_id": "issue:500",
        "url": "https://github.com/test/500",
        "title": "Discussion",
        "state": "open",
        "blocks": [
            {"id": f"issue:500#c{i}", "author": "user", "ts": "2020", "text": "A" * 5000}
            for i in range(10)
        ],
    }
    formatted = format_thread_for_llm(thread, max_chars=14000)
    assert len(formatted) <= 15000
    assert '<thread source_id="issue:500"' in formatted
    assert "[... discussion omitted for brevity ...]" in formatted
