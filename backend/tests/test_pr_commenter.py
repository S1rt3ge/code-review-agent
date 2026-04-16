"""Tests for pr_commenter.build_comment.

Covers:
- No findings → clean message
- Single finding with full fields
- Multiple severities grouped in order
- Duplicate findings hidden from output
- Agent results table rendered in <details>
- Footer shows cost and dedup count
- Long pr_title and head_sha truncation
"""

from decimal import Decimal

from backend.services.pr_commenter import build_comment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(
    severity: str = "high",
    agent: str = "security",
    ftype: str = "sql_injection",
    file_path: str = "app.py",
    line_number: int = 42,
    message: str = "SQL injection risk",
    suggestion: str | None = "Use parameterised query",
    snippet: str | None = None,
    is_duplicate: bool = False,
) -> dict:
    return {
        "severity": severity,
        "agent_name": agent,
        "finding_type": ftype,
        "file_path": file_path,
        "line_number": line_number,
        "message": message,
        "suggestion": suggestion,
        "code_snippet": snippet,
        "is_duplicate": is_duplicate,
    }


def _agent_result(
    status: str = "done",
    findings_count: int = 1,
    tokens_in: int = 100,
    tokens_out: int = 50,
) -> dict:
    return {
        "status": status,
        "findings_count": findings_count,
        "tokens_input": tokens_in,
        "tokens_output": tokens_out,
    }


# ---------------------------------------------------------------------------
# No findings
# ---------------------------------------------------------------------------


def test_no_findings_shows_clean_message():
    body = build_comment([])
    assert "No issues found" in body
    assert "🤖 AI Code Review" in body


def test_no_findings_still_has_header():
    body = build_comment([])
    assert body.startswith("## 🤖 AI Code Review")


# ---------------------------------------------------------------------------
# Header metadata
# ---------------------------------------------------------------------------


def test_pr_title_in_header():
    body = build_comment([], pr_title="Fix login bug")
    assert "> Fix login bug" in body


def test_head_sha_truncated_to_7():
    body = build_comment([], head_sha="abcdef1234567890")
    assert "`abcdef1`" in body


def test_no_head_sha_omitted():
    body = build_comment([])
    assert "Commit:" not in body


# ---------------------------------------------------------------------------
# Single finding
# ---------------------------------------------------------------------------


def test_single_finding_appears():
    f = _finding(
        severity="high", message="SQL injection risk", file_path="db.py", line_number=10
    )
    body = build_comment([f])
    assert "db.py:10" in body
    assert "SQL injection risk" in body


def test_finding_suggestion_shown():
    f = _finding(suggestion="Use parameterised query")
    body = build_comment([f])
    assert "Use parameterised query" in body


def test_finding_snippet_shown():
    f = _finding(snippet="cursor.execute(sql)")
    body = build_comment([f])
    assert "cursor.execute(sql)" in body


def test_finding_no_snippet_no_fences():
    f = _finding(snippet=None)
    body = build_comment([f])
    # No stray code fences from missing snippet
    assert body.count("```") == 0


# ---------------------------------------------------------------------------
# Severity grouping order
# ---------------------------------------------------------------------------


def test_severity_order_critical_before_info():
    findings = [
        _finding(severity="info", message="info msg"),
        _finding(severity="critical", message="critical msg"),
    ]
    body = build_comment(findings)
    assert body.index("critical msg") < body.index("info msg")


def test_all_severity_levels_rendered():
    findings = [
        _finding(severity=s, message=f"{s} msg")
        for s in ["critical", "high", "medium", "low", "info"]
    ]
    body = build_comment(findings)
    for sev in ["Critical", "High", "Medium", "Low", "Info"]:
        assert sev in body


def test_summary_bar_counts():
    findings = [_finding(severity="high")] * 3 + [_finding(severity="low")]
    body = build_comment(findings)
    assert "3 high" in body
    assert "1 low" in body


# ---------------------------------------------------------------------------
# Duplicate handling
# ---------------------------------------------------------------------------


def test_duplicates_hidden_from_output():
    findings = [
        _finding(message="real issue", is_duplicate=False),
        _finding(message="dupe issue", is_duplicate=True),
    ]
    body = build_comment(findings)
    assert "dupe issue" not in body
    assert "real issue" in body


def test_duplicate_count_in_footer():
    findings = [
        _finding(is_duplicate=False),
        _finding(is_duplicate=True),
    ]
    body = build_comment(findings)
    assert "1 duplicate" in body


def test_no_duplicate_count_when_none():
    findings = [_finding(is_duplicate=False)]
    body = build_comment(findings)
    assert "duplicate" not in body


# ---------------------------------------------------------------------------
# Agent results table
# ---------------------------------------------------------------------------


def test_agent_results_table_rendered():
    agent_results = {"security": _agent_result()}
    body = build_comment([_finding()], agent_results=agent_results)
    assert "Agent details" in body
    assert "security" in body


def test_agent_done_shows_checkmark():
    agent_results = {"security": _agent_result(status="done")}
    body = build_comment([_finding()], agent_results=agent_results)
    assert "✅" in body


def test_agent_error_shows_cross():
    agent_results = {"security": _agent_result(status="error")}
    body = build_comment([_finding()], agent_results=agent_results)
    assert "❌" in body


def test_agent_results_hidden_when_none():
    body = build_comment([_finding()], agent_results=None)
    assert "Agent details" not in body


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------


def test_cost_in_footer():
    body = build_comment([_finding()], estimated_cost=Decimal("0.0042"))
    assert "$0.0042" in body


def test_zero_cost_omitted():
    body = build_comment([_finding()], estimated_cost=Decimal("0.0000"))
    assert "$" not in body


def test_footer_has_timestamp():
    body = build_comment([])
    # Footer line contains UTC date pattern
    assert "UTC" in body


def test_finding_count_in_footer_singular():
    body = build_comment([_finding()])
    assert "1 finding" in body


def test_finding_count_in_footer_plural():
    findings = [_finding()] * 3
    body = build_comment(findings)
    assert "3 findings" in body


# ---------------------------------------------------------------------------
# Agent emoji mapping
# ---------------------------------------------------------------------------


def test_security_agent_icon():
    body = build_comment([_finding(agent="security")])
    assert "🔒" in body


def test_performance_agent_icon():
    body = build_comment([_finding(agent="performance", ftype="n_plus_one")])
    assert "⚡" in body


def test_unknown_agent_fallback_icon():
    body = build_comment([_finding(agent="custom_agent")])
    assert "🔍" in body
