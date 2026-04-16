"""Tests for backend/services/result_aggregator.py.

Covers:
    aggregate: deduplication logic, severity ranking, empty input
    group_by_file: grouping correctness
"""

from backend.services.result_aggregator import aggregate, group_by_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _f(
    agent: str,
    ftype: str,
    severity: str,
    file: str = "app.py",
    line: int = 10,
    msg: str = "",
) -> dict:
    return {
        "agent_name": agent,
        "finding_type": ftype,
        "severity": severity,
        "file_path": file,
        "line_number": line,
        "message": msg or f"{ftype} issue",
        "suggestion": None,
        "code_snippet": None,
        "category": agent,
        "is_duplicate": False,
    }


# ---------------------------------------------------------------------------
# aggregate — basic
# ---------------------------------------------------------------------------


def test_aggregate_empty_returns_empty():
    assert aggregate([]) == []


def test_aggregate_single_finding_unchanged():
    f = _f("security", "sql_injection", "critical")
    result = aggregate([f])
    assert len(result) == 1
    assert result[0]["is_duplicate"] is False


def test_aggregate_sorts_by_severity():
    findings = [
        _f("style", "naming", "low", line=1),
        _f("security", "injection", "critical", line=5),
        _f("logic", "null_deref", "high", line=3),
    ]
    result = aggregate(findings)
    severities = [r["severity"] for r in result if not r["is_duplicate"]]
    assert severities == ["critical", "high", "low"]


# ---------------------------------------------------------------------------
# aggregate — deduplication
# ---------------------------------------------------------------------------


def test_aggregate_exact_duplicate_marked():
    """Same file, same line, same type from two agents → second is duplicate."""
    f1 = _f(
        "security",
        "sql_injection",
        "critical",
        line=10,
        msg="SQL injection via f-string",
    )
    f2 = _f("logic", "sql_injection", "high", line=10, msg="SQL injection via f-string")
    result = aggregate([f1, f2])

    non_dup = [r for r in result if not r["is_duplicate"]]
    dup = [r for r in result if r["is_duplicate"]]
    assert len(non_dup) == 1
    assert len(dup) == 1
    # The higher severity (critical) survives
    assert non_dup[0]["severity"] == "critical"


def test_aggregate_nearby_line_same_type_deduplicated():
    """Same type, 2 lines apart → duplicate."""
    f1 = _f("security", "hardcoded_secret", "high", line=10)
    f2 = _f("logic", "hardcoded_secret", "medium", line=12)
    result = aggregate([f1, f2])
    assert sum(1 for r in result if r["is_duplicate"]) == 1


def test_aggregate_different_file_not_duplicate():
    f1 = _f("security", "sql_injection", "critical", file="a.py", line=10)
    f2 = _f("logic", "sql_injection", "critical", file="b.py", line=10)
    result = aggregate([f1, f2])
    assert all(not r["is_duplicate"] for r in result)


def test_aggregate_far_apart_lines_not_duplicate():
    """Same type but 20 lines apart → not duplicate."""
    f1 = _f("security", "xss", "high", line=10)
    f2 = _f("logic", "xss", "high", line=30)
    result = aggregate([f1, f2])
    assert all(not r["is_duplicate"] for r in result)


def test_aggregate_similar_message_deduplicated():
    """Very similar messages, same file/line → duplicate regardless of type."""
    f1 = _f(
        "security",
        "injection",
        "high",
        line=5,
        msg="User input passed directly to SQL query without escaping",
    )
    f2 = _f(
        "logic",
        "unsafe_query",
        "medium",
        line=5,
        msg="User input passed directly to SQL query without sanitisation",
    )
    result = aggregate([f1, f2])
    dup_count = sum(1 for r in result if r["is_duplicate"])
    assert dup_count == 1


def test_aggregate_different_messages_same_type_different_lines_kept():
    f1 = _f(
        "security",
        "missing_auth",
        "high",
        line=10,
        msg="Missing auth check on admin endpoint",
    )
    f2 = _f(
        "security",
        "missing_auth",
        "high",
        line=50,
        msg="Missing auth check on delete endpoint",
    )
    result = aggregate([f1, f2])
    assert all(not r["is_duplicate"] for r in result)


# ---------------------------------------------------------------------------
# group_by_file
# ---------------------------------------------------------------------------


def test_group_by_file_groups_correctly():
    findings = [
        _f("security", "injection", "critical", file="a.py", line=1),
        _f("logic", "null_deref", "high", file="b.py", line=2),
        _f("style", "naming", "low", file="a.py", line=3),
    ]
    groups = group_by_file(findings)
    assert set(groups.keys()) == {"a.py", "b.py"}
    assert len(groups["a.py"]) == 2
    assert len(groups["b.py"]) == 1


def test_group_by_file_empty():
    assert group_by_file([]) == {}


def test_group_by_file_single_file():
    findings = [_f("security", "xss", "high", file="main.py") for _ in range(5)]
    groups = group_by_file(findings)
    assert list(groups.keys()) == ["main.py"]
    assert len(groups["main.py"]) == 5
