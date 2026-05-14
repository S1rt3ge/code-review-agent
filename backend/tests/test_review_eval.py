"""Tests for deterministic review quality evals."""

import json
from pathlib import Path

import pytest

from backend.services.review_eval import (
    ExpectedFinding,
    ReviewEvalCase,
    load_eval_cases,
    run_review_quality_eval,
)


def test_bundled_review_quality_evals_pass() -> None:
    cases = load_eval_cases(Path("evals/review_quality_cases.json"))

    report = run_review_quality_eval(cases)

    assert report.passed is True
    assert report.cases_total == 6
    assert report.cases_passed == 6
    assert report.expected_recall == 1.0
    assert report.unexpected_findings == 0


def test_eval_report_fails_when_expected_finding_is_missing() -> None:
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
+print("safe")
"""
    case = ReviewEvalCase(
        id="missing-security-finding",
        title="Missing expected security finding",
        code_diff=diff,
        selected_agents=("security",),
        expected_findings=(
            ExpectedFinding(agent_name="security", finding_type="unsafe_eval"),
        ),
    )

    report = run_review_quality_eval([case])

    assert report.passed is False
    assert report.cases_passed == 0
    assert report.expected_recall == 0.0
    assert report.case_results[0].missing_expected[0].finding_type == "unsafe_eval"


def test_eval_report_fails_on_unexpected_finding() -> None:
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
+result = eval(user_input)
"""
    case = ReviewEvalCase(
        id="unexpected-security-finding",
        title="Unexpected security finding",
        code_diff=diff,
        selected_agents=("security",),
        expected_findings=(),
        max_unexpected_findings=0,
    )

    report = run_review_quality_eval([case])

    assert report.passed is False
    assert report.unexpected_findings == 1
    assert report.case_results[0].unexpected_actual[0].finding_type == "unsafe_eval"


def test_load_eval_cases_rejects_empty_case_file(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="at least one"):
        load_eval_cases(path)


def test_load_eval_cases_rejects_missing_required_fields(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": [{"id": "broken"}]}), encoding="utf-8")

    with pytest.raises(ValueError, match="title"):
        load_eval_cases(path)
