"""Tests for Review Passport markdown export formatting."""

from datetime import datetime, timezone

from backend.services.review_passport_commenter import build_passport_markdown


def _passport(**overrides):
    base = {
        "mode": "combined",
        "spec_source_type": "manual",
        "spec_source_ref": "Issue #53",
        "verdict": "READY_WITH_RISKS",
        "confidence_score": 78,
        "coverage_summary": [
            {
                "criterion_id": "AC-1",
                "criterion": "User can run local demo",
                "status": "covered",
                "evidence": [{"summary": "Added line matches the criterion."}],
            }
        ],
        "anti_slop_signals": [
            {
                "type": "missing_tests",
                "severity": "medium",
                "summary": "Application code changed without matching test changes",
                "suggestion": "Add focused tests for the changed behavior.",
            }
        ],
        "missing_evidence": [],
        "qa_steps": [
            {
                "step": 1,
                "title": "Run local stack",
                "command": "docker compose up --build",
                "expected": "Frontend is available at http://localhost:5173",
            }
        ],
        "generated_at": datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return base


def test_build_passport_markdown_includes_verdict_and_criteria() -> None:
    body = build_passport_markdown(
        _passport(),
        pr_title="Improve local demo",
        head_sha="abcdef123456",
    )

    assert body.startswith("<!-- code-review-agent:review-passport -->")
    assert "## Review Passport" in body
    assert "Improve local demo" in body
    assert "`abcdef1`" in body
    assert "**Verdict:** READY_WITH_RISKS" in body
    assert "User can run local demo" in body
    assert "Added line matches the criterion." in body


def test_build_passport_markdown_includes_anti_slop_and_qa() -> None:
    body = build_passport_markdown(_passport())

    assert "Anti-AI-Slop Signals" in body
    assert "Application code changed without matching test changes" in body
    assert "Manual QA Script" in body
    assert "docker compose up --build" in body


def test_build_passport_markdown_truncates_long_sections() -> None:
    passport = _passport(
        coverage_summary=[
            {
                "criterion_id": f"AC-{index}",
                "criterion": f"Criterion {index}",
                "status": "missing",
                "evidence": [],
            }
            for index in range(1, 13)
        ],
    )

    body = build_passport_markdown(passport)

    assert "Criterion 10" in body
    assert "Criterion 11" not in body
    assert "2 more criteria omitted" in body
