"""Citation verifier and evidence validator for Decision Archaeologist."""

import re
from typing import Any

from pydantic import BaseModel


class Citation(BaseModel):
    """Citation referencing a verified evidence quote from the graph."""

    n: int
    evidence_id: str
    quote: str
    url: str
    author: str
    ts: str
    decision_id: str | None = None


class Verification(BaseModel):
    """Trust badge payload measuring verified vs invalid claims."""

    valid: int
    invalid: int
    repaired: bool


class VerificationCheck(BaseModel):
    """Intermediate check status to decide if a repair turn is required."""

    is_valid: bool
    valid_ids: list[str]
    invalid_ids: list[str]
    flagged_sentences: list[str]
    repair_prompt: str | None = None


# Regex matching [[ev:ID]] markers
EVIDENCE_MARKER_REGEX = re.compile(r"\[\[ev:([a-zA-Z0-9_\-:]+)\]\]")

# Regex heuristics indicating factual claims that demand citation
FACTUAL_PATTERNS = [
    re.compile(r"\b(19\d\d|20\d\d)\b"),
    re.compile(r"(?<!\w)#\d+\b"),
    re.compile(
        r"(?i)\b(decid\w*|deprecat\w*|remov\w*|dropp\w*|merg\w*|breaking|supersed\w*|revers\w*)\b"
    ),
]


def extract_markers(text: str) -> list[str]:
    """Extract all [[ev:ID]] marker strings from text in order."""
    return EVIDENCE_MARKER_REGEX.findall(text)


def extract_sentences(text: str) -> list[str]:
    """Split text into sentences while ignoring markdown list prefixes."""
    raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    cleaned = []
    for s in raw_sentences:
        clean = s.strip()
        if clean and not clean.startswith("#"):
            cleaned.append(clean)
    return cleaned


def collect_evidence_from_tool_results(
    tool_results: list[dict[str, Any]],
    graph: Any | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a lookup map of evidence_id -> metadata from all tool calls in the turn."""
    evidence_map: dict[str, dict[str, Any]] = {}

    for res in tool_results:
        data = res.get("data")
        # 1. From trace_to_source / evidence list
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "id" in item:
                    eid = item["id"]
                    evidence_map[eid] = {
                        "evidence_id": eid,
                        "quote": item.get("quote", ""),
                        "url": item.get("url", ""),
                        "author": item.get("author", ""),
                        "ts": item.get("ts", ""),
                        "decision_id": item.get("decision_id"),
                    }
        # 2. From get_decision
        elif isinstance(data, dict):
            dec_id = data.get("id")
            for ev in data.get("evidence", []):
                eid = ev.get("id")
                if eid:
                    evidence_map[eid] = {
                        "evidence_id": eid,
                        "quote": ev.get("quote", ""),
                        "url": ev.get("url", ""),
                        "author": ev.get("author", ""),
                        "ts": ev.get("ts", ""),
                        "decision_id": dec_id or ev.get("decision_id"),
                    }

        # 3. From graph_elements nodes
        graph_elem = res.get("graph_elements", {})
        if isinstance(graph_elem, dict):
            for node in graph_elem.get("nodes", []):
                if node.get("label") == "Evidence":
                    eid = node.get("id", "").replace("Evidence:", "")
                    if eid and eid not in evidence_map:
                        props = node.get("props", {})
                        evidence_map[eid] = {
                            "evidence_id": eid,
                            "quote": props.get("quote", ""),
                            "url": props.get("url", ""),
                            "author": props.get("author", ""),
                            "ts": props.get("ts", ""),
                            "decision_id": props.get("decision_id"),
                        }

    # If graph is provided and some evidence nodes lack props, enrich them
    if graph and evidence_map:
        missing_quotes = [eid for eid, ev in evidence_map.items() if not ev.get("quote")]
        if missing_quotes:
            try:
                cypher = """
                MATCH (e:Evidence)
                WHERE e.id IN $eids
                OPTIONAL MATCH (d:Decision)-[:SUPPORTED_BY]->(e)
                RETURN e.id, e.quote, e.url, e.author, e.ts, d.id
                """
                res = graph.query(cypher, params={"eids": missing_quotes})
                if res.result_set:
                    for row in res.result_set:
                        eid = row[0]
                        if eid in evidence_map:
                            evidence_map[eid]["quote"] = row[1] or evidence_map[eid]["quote"]
                            evidence_map[eid]["url"] = row[2] or evidence_map[eid]["url"]
                            evidence_map[eid]["author"] = row[3] or evidence_map[eid]["author"]
                            evidence_map[eid]["ts"] = str(row[4] or evidence_map[eid]["ts"])
                            if row[5]:
                                evidence_map[eid]["decision_id"] = row[5]
            except Exception:
                pass

    return evidence_map


def check_citations(
    text: str,
    known_evidence_ids: set[str],
) -> VerificationCheck:
    """Evaluate marker validity and flag unverified factual sentences."""
    markers = extract_markers(text)
    valid_ids: list[str] = []
    invalid_ids: list[str] = []

    for m in markers:
        # Check either exact id or normalized
        clean_m = m.replace("Evidence:", "")
        if clean_m in known_evidence_ids or m in known_evidence_ids:
            valid_ids.append(m)
        else:
            invalid_ids.append(m)

    # Detect factual claims missing any citation marker
    sentences = extract_sentences(text)
    flagged: list[str] = []
    for s in sentences:
        has_marker = bool(EVIDENCE_MARKER_REGEX.search(s))
        if not has_marker:
            is_factual = any(p.search(s) for p in FACTUAL_PATTERNS)
            if is_factual:
                flagged.append(s)

    is_valid = (len(invalid_ids) == 0) and (len(flagged) == 0)

    repair_prompt = None
    if not is_valid:
        issues = []
        if invalid_ids:
            issues.append(f"unrecognized evidence IDs: {', '.join(invalid_ids)}")
        if flagged:
            issues.append(f"uncited factual claims: '{'; '.join(flagged[:2])}'")
        issues_str = "; ".join(issues)
        repair_prompt = (
            f"These claims lack valid evidence: [{issues_str}]. "
            "Rewrite the answer using ONLY tool-returned evidence ids, or remove the claims."
        )

    return VerificationCheck(
        is_valid=is_valid,
        valid_ids=valid_ids,
        invalid_ids=invalid_ids,
        flagged_sentences=flagged,
        repair_prompt=repair_prompt,
    )


def finalize_answer(
    text: str,
    evidence_map: dict[str, dict[str, Any]],
    was_repaired: bool = False,
) -> tuple[str, list[Citation], Verification]:
    """Convert valid [[ev:ID]] markers to [1], [2], strip invalid markers, and return Citations."""
    valid_ids_seen: list[str] = []
    id_to_num: dict[str, int] = {}
    citations: list[Citation] = []

    invalid_count = 0

    def marker_replacer(match: re.Match) -> str:
        nonlocal invalid_count
        raw_id = match.group(1)
        clean_id = raw_id.replace("Evidence:", "")

        target_id = None
        if clean_id in evidence_map:
            target_id = clean_id
        elif raw_id in evidence_map:
            target_id = raw_id

        if target_id is not None:
            if target_id not in id_to_num:
                num = len(id_to_num) + 1
                id_to_num[target_id] = num
                valid_ids_seen.append(target_id)
                info = evidence_map[target_id]
                citations.append(
                    Citation(
                        n=num,
                        evidence_id=target_id,
                        quote=info.get("quote", ""),
                        url=info.get("url", ""),
                        author=info.get("author", ""),
                        ts=str(info.get("ts", "")),
                        decision_id=info.get("decision_id"),
                    )
                )
            return f"[{id_to_num[target_id]}]"
        else:
            invalid_count += 1
            return " (Not verified against the graph)"

    final_markdown = EVIDENCE_MARKER_REGEX.sub(marker_replacer, text)

    verification = Verification(
        valid=len(valid_ids_seen),
        invalid=invalid_count,
        repaired=was_repaired,
    )

    return final_markdown, citations, verification
