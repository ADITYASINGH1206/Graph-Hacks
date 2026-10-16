"""Deterministic text ranking for decision search.

Fulltext OR-matching alone ranks badly on version-heavy questions: it ignored numbers, so
"Why was Python 3.6 dropped?" ranked the Python 2 decision first and "python 2" ranked
the 3.6 decision first. These helpers keep version tokens (``3.6``, ``2``) whole and make an
exact version match count for much more than a shared word like "python".
"""

import re

_TOKEN_RE = re.compile(r"\d+(?:\.\d+)*|[a-z]+")
_VERSION_RE = re.compile(r"^\d+(?:\.\d+)*$")

STOPWORDS = frozenset(
    """a an and are as at be been by did do does for from had has have how i in is it its of on
    or our that the their there this to was were what when where which who why will with
    about after before change changed decision decisions""".split()
)

W_TITLE = 3.0
W_MODULE = 2.5
W_SUMMARY = 1.0
W_VERSION = 8.0


def _stem(word: str) -> str:
    """Very small suffix stripper so 'dropped', 'dropping' and 'drop' match."""
    if _VERSION_RE.match(word) or len(word) <= 3:
        return word
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeiou":
        word = word[:-1]  # dropp -> drop
    return word


def tokenize(text: str) -> list[str]:
    """Lowercase tokens; version numbers stay whole ('3.6'); words are stemmed."""
    return [_stem(t) for t in _TOKEN_RE.findall((text or "").lower())]


def query_terms(query: str) -> tuple[list[str], list[str]]:
    """Return (word_terms, version_terms) for a query, without stopwords."""
    words: list[str] = []
    versions: list[str] = []
    for tok in tokenize(query):
        if _VERSION_RE.match(tok):
            if tok not in versions:
                versions.append(tok)
        elif tok not in STOPWORDS and tok not in words:
            words.append(tok)
    return words, versions


def score_decision(
    query: str, title: str, summary: str, modules: list[str], decision_type: str = ""
) -> float:
    """Relevance of one decision to a query (0 means no match)."""
    words, versions = query_terms(query)
    if not words and not versions:
        return 0.0
    title_t = set(tokenize(title))
    summary_t = set(tokenize(summary))
    module_t = {t for m in modules for t in tokenize(m)}
    type_t = set(tokenize(decision_type))

    score = 0.0
    for w in words:
        if w in title_t:
            score += W_TITLE
        if w in module_t:
            score += W_MODULE
        if w in summary_t:
            score += W_SUMMARY
        if w in type_t:
            score += 0.5
    for v in versions:
        if v in title_t:
            score += W_VERSION
        elif v in summary_t:
            score += W_VERSION / 2
    # A version in the query that is absent from the text is a mismatch: 'python 2' must not
    # surface the 3.6 decision just because both say 'python'.
    if versions and not any(v in title_t or v in summary_t for v in versions):
        score *= 0.2
    return score
