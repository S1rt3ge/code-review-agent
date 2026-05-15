"""Tests for Review Passport merge gate mapping."""

from datetime import datetime, timezone
from types import SimpleNamespace

from backend.services.review_passport_gate import (
    GITHUB_STATUS_CONTEXT,
    build_passport_gate,
)


def _passport(verdict: str, **overrides):
    base = {
        "verdict": verdict,
        "confidence_score": 90,
        "github_gate_state": None,
        "github_gate_url": None,
        "github_gate_posted_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_passport_gate_marks_ready_as_success() -> None:
    gate = build_passport_gate(_passport("READY", confidence_score=96))

    assert gate["context"] == GITHUB_STATUS_CONTEXT
    assert gate["state"] == "success"
    assert gate["required_action"] == "merge_ready"
    assert gate["description"] == "Review Passport READY: evidence covers merge criteria."


def test_build_passport_gate_fails_risky_and_blocked_verdicts() -> None:
    risky_gate = build_passport_gate(_passport("READY_WITH_RISKS"))
    blocked_gate = build_passport_gate(_passport("BLOCKED"))

    assert risky_gate["state"] == "failure"
    assert risky_gate["required_action"] == "review_risks"
    assert blocked_gate["state"] == "failure"
    assert blocked_gate["required_action"] == "fix_blockers"


def test_build_passport_gate_keeps_last_github_metadata() -> None:
    posted_at = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)

    gate = build_passport_gate(
        _passport(
            "READY",
            github_gate_state="success",
            github_gate_url="https://api.github.com/repos/test/repo/statuses/abc",
            github_gate_posted_at=posted_at,
        )
    )

    assert gate["github_gate_state"] == "success"
    assert gate["github_gate_url"].endswith("/statuses/abc")
    assert gate["github_gate_posted_at"] == posted_at
