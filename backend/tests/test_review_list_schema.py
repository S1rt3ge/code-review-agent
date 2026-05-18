"""Tests for review list response shaping."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from backend.models.schemas import ReviewListItem


def _review(**overrides):
    values = {
        "id": uuid4(),
        "repo_id": uuid4(),
        "github_pr_number": 17,
        "github_pr_title": "Add passport signal",
        "status": "done",
        "total_findings": 0,
        "lm_used": "local-deterministic",
        "created_at": datetime(2026, 5, 18, tzinfo=UTC),
        "completed_at": None,
        "passport": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_review_list_item_includes_passport_summary() -> None:
    passport = SimpleNamespace(
        verdict="READY_WITH_RISKS",
        confidence_score=82,
        spec_source_type="review_dna",
        generated_at=datetime(2026, 5, 18, 12, 30, tzinfo=UTC),
        github_gate_state="failure",
        estimated_cost=Decimal("0"),
    )

    item = ReviewListItem.model_validate(_review(passport=passport))

    assert item.passport is not None
    assert item.passport.verdict == "READY_WITH_RISKS"
    assert item.passport.confidence_score == 82
    assert item.passport.spec_source_type == "review_dna"
    assert item.passport.github_gate_state == "failure"


def test_review_list_item_allows_missing_passport() -> None:
    item = ReviewListItem.model_validate(_review())

    assert item.passport is None
