"""Tests for lightweight Review Passport list summaries."""

from datetime import UTC, datetime
from types import SimpleNamespace

from backend.services.review_passport_summary import build_review_passport_summary


def _passport(**overrides):
    values = {
        "verdict": "READY_WITH_RISKS",
        "confidence_score": 76,
        "spec_source_type": "review_dna",
        "generated_at": datetime(2026, 5, 18, 12, 30, tzinfo=UTC),
        "github_gate_state": "failure",
        "coverage_summary": [],
        "anti_slop_signals": [],
        "missing_evidence": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_build_review_passport_summary_counts_non_ready_reasons() -> None:
    summary = build_review_passport_summary(
        _passport(
            verdict="BLOCKED",
            coverage_summary=[
                {"status": "missing", "criterion": "Private acceptance criteria"},
                {"status": "risky", "criterion": "Internal launch checklist"},
                {"status": "covered", "criterion": "Visible evidence"},
            ],
            anti_slop_signals=[
                {"type": "missing_tests", "summary": "Application code changed without tests"},
                {"type": "placeholder_code", "summary": "Placeholder code remains"},
            ],
            missing_evidence=[
                {"criterion": "Sensitive customer-specific requirement"},
            ],
        )
    )

    assert summary["verdict"] == "BLOCKED"
    assert summary["missing_evidence_count"] == 1
    assert summary["anti_slop_signal_count"] == 2
    assert summary["risky_criteria_count"] == 2
    assert summary["readiness_reason"] == "1 missing evidence item, 2 anti-slop signals"
    assert "Sensitive customer-specific requirement" not in summary["readiness_reason"]
    assert "Private acceptance criteria" not in summary["readiness_reason"]


def test_build_review_passport_summary_marks_ready_without_noise() -> None:
    summary = build_review_passport_summary(
        _passport(
            verdict="READY",
            confidence_score=98,
            github_gate_state="success",
            coverage_summary=[{"status": "covered", "criterion": "Local demo works"}],
        )
    )

    assert summary["readiness_reason"] == "Evidence covers merge criteria"
    assert summary["missing_evidence_count"] == 0
    assert summary["anti_slop_signal_count"] == 0
    assert summary["risky_criteria_count"] == 0
