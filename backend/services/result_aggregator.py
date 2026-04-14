"""Finding deduplication, ranking, and grouping.

Takes the raw flat list of findings from all agents and produces a clean,
deduplicated, severity-ranked output suitable for storage and display.

Functions:
    aggregate: Main entry point — dedup, rank, and return findings.
    group_by_file: Group an aggregated list by file path for display.
"""

import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Severity order: lower index = higher priority.
SEVERITY_RANK: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}

# Two findings on the same file/line are considered duplicates if their
# messages are at least this similar (0–1 scale).
_SIMILARITY_THRESHOLD = 0.70

# Findings on the same file within this many lines of each other and with the
# same finding_type are considered positional duplicates.
_LINE_PROXIMITY = 3


def _severity_key(finding: dict) -> int:
    """Return numeric sort key for severity (lower = more severe)."""
    return SEVERITY_RANK.get(finding.get("severity", "info"), 4)


def _message_similarity(a: str, b: str) -> float:
    """Return SequenceMatcher ratio between two strings (0–1)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _is_duplicate(candidate: dict, existing: list[dict]) -> bool:
    """Return True if candidate is a near-duplicate of any finding in existing.

    Two findings are duplicates when ALL of the following hold:
    - Same file_path
    - Line numbers within _LINE_PROXIMITY of each other
    - Same finding_type OR message similarity >= _SIMILARITY_THRESHOLD

    Args:
        candidate: Finding dict to check.
        existing: List of already-accepted findings.

    Returns:
        True if a duplicate is found.
    """
    c_file = candidate.get("file_path", "")
    c_line = int(candidate.get("line_number", 0))
    c_type = candidate.get("finding_type", "")
    c_msg = candidate.get("message", "")

    for ex in existing:
        if ex.get("file_path") != c_file:
            continue
        ex_line = int(ex.get("line_number", 0))
        if abs(ex_line - c_line) > _LINE_PROXIMITY:
            continue
        # Same type or similar message → duplicate
        same_type = ex.get("finding_type") == c_type
        similar_msg = _message_similarity(c_msg, ex.get("message", "")) >= _SIMILARITY_THRESHOLD
        if same_type or similar_msg:
            return True

    return False


def aggregate(findings: list[dict]) -> list[dict]:
    """Deduplicate and rank findings from all agents.

    Processing steps:
    1. Sort input by severity so the most severe variant of a duplicate is kept.
    2. Walk sorted list; mark near-duplicates with ``is_duplicate=True``.
    3. Return the full list sorted by severity (duplicates at the end within
       each severity group so they can be filtered easily).

    Args:
        findings: Flat list of raw finding dicts from all agents.

    Returns:
        Deduplicated list sorted by severity (critical first).
    """
    if not findings:
        return []

    # Sort by severity first so the highest-severity copy of a duplicate wins.
    sorted_input = sorted(findings, key=_severity_key)

    accepted: list[dict] = []
    duplicates: list[dict] = []

    for finding in sorted_input:
        if _is_duplicate(finding, accepted):
            dup = dict(finding)
            dup["is_duplicate"] = True
            duplicates.append(dup)
            logger.debug(
                "Marked duplicate: %s in %s:%s",
                finding.get("finding_type"),
                finding.get("file_path"),
                finding.get("line_number"),
            )
        else:
            clean = dict(finding)
            clean["is_duplicate"] = False
            accepted.append(clean)

    total_dup = len(duplicates)
    if total_dup:
        logger.info("Deduplicated %d findings (%d duplicates removed)", len(findings), total_dup)

    # Final sort: non-duplicates by severity, then duplicates by severity.
    result = sorted(accepted, key=_severity_key) + sorted(duplicates, key=_severity_key)
    return result


def group_by_file(findings: list[dict]) -> dict[str, list[dict]]:
    """Group findings by file path, preserving severity order within each file.

    Args:
        findings: Aggregated findings list (output of ``aggregate``).

    Returns:
        Dict mapping file_path → list of findings for that file.
    """
    groups: dict[str, list[dict]] = {}
    for f in findings:
        path = f.get("file_path", "unknown")
        groups.setdefault(path, []).append(f)
    return groups
