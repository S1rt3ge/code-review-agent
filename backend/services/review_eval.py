"""Deterministic quality evals for the local review analyzer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.services.playground_review import (
    LocalFinding,
    analyze_diff_locally,
    validate_playground_diff,
)
from backend.services.review_passport import (
    detect_anti_slop_signals,
    snapshot_diff,
)


@dataclass(frozen=True)
class ExpectedFinding:
    """Expected finding descriptor from an eval case."""

    agent_name: str
    finding_type: str
    file_path: str | None = None
    line_number: int | None = None
    severity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "agent_name": self.agent_name,
            "finding_type": self.finding_type,
        }
        if self.file_path is not None:
            payload["file_path"] = self.file_path
        if self.line_number is not None:
            payload["line_number"] = self.line_number
        if self.severity is not None:
            payload["severity"] = self.severity
        return payload


@dataclass(frozen=True)
class ExpectedPassportSignal:
    """Expected Review Passport anti-slop signal descriptor from an eval case."""

    signal_type: str
    severity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {"type": self.signal_type}
        if self.severity is not None:
            payload["severity"] = self.severity
        return payload


@dataclass(frozen=True)
class ReviewEvalCase:
    """Single deterministic review quality eval case."""

    id: str
    title: str
    code_diff: str
    selected_agents: tuple[str, ...]
    expected_findings: tuple[ExpectedFinding, ...]
    expected_passport_signals: tuple[ExpectedPassportSignal, ...] = ()
    max_unexpected_findings: int = 0
    max_unexpected_passport_signals: int = 0


@dataclass(frozen=True)
class MatchedFinding:
    """Expected finding matched to an actual analyzer finding."""

    expected: ExpectedFinding
    actual: LocalFinding

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected": self.expected.to_dict(),
            "actual": _finding_to_dict(self.actual),
        }


@dataclass(frozen=True)
class MatchedPassportSignal:
    """Expected passport signal matched to an actual anti-slop signal."""

    expected: ExpectedPassportSignal
    actual: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected": self.expected.to_dict(),
            "actual": self.actual,
        }


@dataclass(frozen=True)
class CaseEvalResult:
    """Result for one eval case."""

    case: ReviewEvalCase
    matched_expected: tuple[MatchedFinding, ...]
    missing_expected: tuple[ExpectedFinding, ...]
    unexpected_actual: tuple[LocalFinding, ...]
    matched_passport_signals: tuple[MatchedPassportSignal, ...] = ()
    missing_passport_signals: tuple[ExpectedPassportSignal, ...] = ()
    unexpected_passport_signals: tuple[dict[str, Any], ...] = ()

    @property
    def passed(self) -> bool:
        return (
            not self.missing_expected
            and not self.missing_passport_signals
            and len(self.unexpected_actual) <= self.case.max_unexpected_findings
            and len(self.unexpected_passport_signals)
            <= self.case.max_unexpected_passport_signals
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.case.id,
            "title": self.case.title,
            "passed": self.passed,
            "selected_agents": list(self.case.selected_agents),
            "matched_expected": [
                matched.to_dict() for matched in self.matched_expected
            ],
            "missing_expected": [
                expected.to_dict() for expected in self.missing_expected
            ],
            "unexpected_actual": [
                _finding_to_dict(finding) for finding in self.unexpected_actual
            ],
            "matched_passport_signals": [
                matched.to_dict() for matched in self.matched_passport_signals
            ],
            "missing_passport_signals": [
                expected.to_dict() for expected in self.missing_passport_signals
            ],
            "unexpected_passport_signals": list(self.unexpected_passport_signals),
            "max_unexpected_findings": self.case.max_unexpected_findings,
            "max_unexpected_passport_signals": (
                self.case.max_unexpected_passport_signals
            ),
        }


@dataclass(frozen=True)
class ReviewEvalReport:
    """Aggregate report for a review quality eval run."""

    case_results: tuple[CaseEvalResult, ...]

    @property
    def cases_total(self) -> int:
        return len(self.case_results)

    @property
    def cases_passed(self) -> int:
        return sum(1 for result in self.case_results if result.passed)

    @property
    def expected_total(self) -> int:
        return sum(
            len(result.case.expected_findings) for result in self.case_results
        )

    @property
    def expected_matched(self) -> int:
        return sum(len(result.matched_expected) for result in self.case_results)

    @property
    def expected_recall(self) -> float:
        if self.expected_total == 0:
            return 1.0
        return self.expected_matched / self.expected_total

    @property
    def passport_signals_expected_total(self) -> int:
        return sum(
            len(result.case.expected_passport_signals)
            for result in self.case_results
        )

    @property
    def passport_signals_matched(self) -> int:
        return sum(
            len(result.matched_passport_signals) for result in self.case_results
        )

    @property
    def passport_signal_recall(self) -> float:
        if self.passport_signals_expected_total == 0:
            return 1.0
        return self.passport_signals_matched / self.passport_signals_expected_total

    @property
    def unexpected_findings(self) -> int:
        return sum(len(result.unexpected_actual) for result in self.case_results)

    @property
    def unexpected_passport_signals(self) -> int:
        return sum(
            len(result.unexpected_passport_signals) for result in self.case_results
        )

    @property
    def case_pass_rate(self) -> float:
        if self.cases_total == 0:
            return 0.0
        return self.cases_passed / self.cases_total

    @property
    def score(self) -> float:
        return round(
            (
                (
                    self.case_pass_rate
                    + self.expected_recall
                    + self.passport_signal_recall
                )
                / 3
            )
            * 100,
            1,
        )

    @property
    def passed(self) -> bool:
        return self.cases_total > 0 and all(
            result.passed for result in self.case_results
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "cases_total": self.cases_total,
            "cases_passed": self.cases_passed,
            "expected_total": self.expected_total,
            "expected_matched": self.expected_matched,
            "expected_recall": self.expected_recall,
            "passport_signals_expected_total": self.passport_signals_expected_total,
            "passport_signals_matched": self.passport_signals_matched,
            "passport_signal_recall": self.passport_signal_recall,
            "unexpected_findings": self.unexpected_findings,
            "unexpected_passport_signals": self.unexpected_passport_signals,
            "case_results": [result.to_dict() for result in self.case_results],
        }


def load_eval_cases(path: Path) -> list[ReviewEvalCase]:
    """Load and validate review eval cases from JSON."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid eval JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("eval fixture root must be an object")

    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("eval fixture must contain at least one case")

    return [
        _case_from_mapping(raw_case, f"cases[{index}]")
        for index, raw_case in enumerate(raw_cases)
    ]


def run_review_quality_eval(cases: list[ReviewEvalCase]) -> ReviewEvalReport:
    """Run deterministic review quality evals."""
    if not cases:
        raise ValueError("review quality eval requires at least one case")

    return ReviewEvalReport(
        case_results=tuple(_evaluate_case(case) for case in cases)
    )


def format_review_eval_report(report: ReviewEvalReport) -> str:
    """Format a terminal-friendly eval report."""
    recall_percent = report.expected_recall * 100
    lines = [
        "Review Quality Eval",
        "===================",
        f"Cases: {report.cases_passed}/{report.cases_total} passed",
        (
            "Expected recall: "
            f"{report.expected_matched}/{report.expected_total} "
            f"({recall_percent:.1f}%)"
        ),
        (
            "Passport signal recall: "
            f"{report.passport_signals_matched}/"
            f"{report.passport_signals_expected_total} "
            f"({report.passport_signal_recall * 100:.1f}%)"
        ),
        f"Unexpected findings: {report.unexpected_findings}",
        f"Unexpected passport signals: {report.unexpected_passport_signals}",
        f"Score: {report.score:.1f}/100",
        "",
    ]

    for result in report.case_results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"[{status}] {result.case.id} - {result.case.title}")

        for missing in result.missing_expected:
            lines.append(
                "  missing: "
                f"{missing.agent_name}/{missing.finding_type}"
                f"{_expected_location(missing)}"
            )

        for unexpected in result.unexpected_actual:
            lines.append(
                "  unexpected: "
                f"{unexpected.agent_name}/{unexpected.finding_type}"
                f" at {unexpected.file_path}:{unexpected.line_number}"
            )

        for missing in result.missing_passport_signals:
            lines.append(f"  missing passport signal: {missing.signal_type}")

        for unexpected in result.unexpected_passport_signals:
            lines.append(
                "  unexpected passport signal: "
                f"{unexpected.get('type', 'unknown')}"
            )

    return "\n".join(lines)


def _evaluate_case(case: ReviewEvalCase) -> CaseEvalResult:
    actual_findings = analyze_diff_locally(case.code_diff, list(case.selected_agents))
    actual_signals = _detect_case_passport_signals(case)
    unmatched_actual = list(actual_findings)
    unmatched_signals = list(actual_signals)
    matched: list[MatchedFinding] = []
    missing: list[ExpectedFinding] = []
    matched_signals: list[MatchedPassportSignal] = []
    missing_signals: list[ExpectedPassportSignal] = []

    for expected in case.expected_findings:
        match_index = _find_match_index(expected, unmatched_actual)
        if match_index is None:
            missing.append(expected)
            continue

        matched.append(
            MatchedFinding(
                expected=expected,
                actual=unmatched_actual.pop(match_index),
            )
        )

    for expected in case.expected_passport_signals:
        match_index = _find_signal_match_index(expected, unmatched_signals)
        if match_index is None:
            missing_signals.append(expected)
            continue

        matched_signals.append(
            MatchedPassportSignal(
                expected=expected,
                actual=unmatched_signals.pop(match_index),
            )
        )

    return CaseEvalResult(
        case=case,
        matched_expected=tuple(matched),
        missing_expected=tuple(missing),
        unexpected_actual=tuple(unmatched_actual),
        matched_passport_signals=tuple(matched_signals),
        missing_passport_signals=tuple(missing_signals),
        unexpected_passport_signals=tuple(unmatched_signals),
    )


def _find_match_index(
    expected: ExpectedFinding,
    actual_findings: list[LocalFinding],
) -> int | None:
    for index, actual in enumerate(actual_findings):
        if _matches_expected(expected, actual):
            return index
    return None


def _detect_case_passport_signals(case: ReviewEvalCase) -> list[dict[str, Any]]:
    if not case.expected_passport_signals:
        return []
    snapshot = snapshot_diff(case.code_diff)
    return detect_anti_slop_signals(
        snapshot["changed_files"],
        snapshot["added_lines"],
    )


def _matches_expected(expected: ExpectedFinding, actual: LocalFinding) -> bool:
    if actual.agent_name != expected.agent_name:
        return False
    if actual.finding_type != expected.finding_type:
        return False
    if expected.file_path is not None and actual.file_path != expected.file_path:
        return False
    if expected.line_number is not None and actual.line_number != expected.line_number:
        return False
    return not (expected.severity is not None and actual.severity != expected.severity)


def _find_signal_match_index(
    expected: ExpectedPassportSignal,
    actual_signals: list[dict[str, Any]],
) -> int | None:
    for index, actual in enumerate(actual_signals):
        if _matches_signal_expected(expected, actual):
            return index
    return None


def _matches_signal_expected(
    expected: ExpectedPassportSignal,
    actual: dict[str, Any],
) -> bool:
    if actual.get("type") != expected.signal_type:
        return False
    return not (
        expected.severity is not None and actual.get("severity") != expected.severity
    )


def _case_from_mapping(raw: Any, context: str) -> ReviewEvalCase:
    mapping = _require_mapping(raw, context)
    case_id = _require_str(mapping, "id", context)
    title = _require_str(mapping, "title", context)
    code_diff = validate_playground_diff(_require_str(mapping, "code_diff", context))
    selected_agents = tuple(_require_str_list(mapping, "selected_agents", context))
    expected_findings = tuple(
        _expected_from_mapping(raw_expected, f"{context}.expected_findings[{index}]")
        for index, raw_expected in enumerate(
            _optional_list(mapping, "expected_findings", context)
        )
    )
    expected_passport_signals = tuple(
        _expected_signal_from_mapping(
            raw_expected,
            f"{context}.expected_passport_signals[{index}]",
        )
        for index, raw_expected in enumerate(
            _optional_list(mapping, "expected_passport_signals", context)
        )
    )
    max_unexpected_findings = _optional_non_negative_int(
        mapping,
        "max_unexpected_findings",
        context,
        default=0,
    )
    max_unexpected_passport_signals = _optional_non_negative_int(
        mapping,
        "max_unexpected_passport_signals",
        context,
        default=0,
    )

    if not selected_agents and not expected_passport_signals:
        raise ValueError(
            f"{context}.selected_agents must contain at least one agent "
            "unless expected_passport_signals are provided"
        )

    return ReviewEvalCase(
        id=case_id,
        title=title,
        code_diff=code_diff,
        selected_agents=selected_agents,
        expected_findings=expected_findings,
        expected_passport_signals=expected_passport_signals,
        max_unexpected_findings=max_unexpected_findings,
        max_unexpected_passport_signals=max_unexpected_passport_signals,
    )


def _expected_from_mapping(raw: Any, context: str) -> ExpectedFinding:
    mapping = _require_mapping(raw, context)
    return ExpectedFinding(
        agent_name=_require_str(mapping, "agent_name", context),
        finding_type=_require_str(mapping, "finding_type", context),
        file_path=_optional_str(mapping, "file_path", context),
        line_number=_optional_int(mapping, "line_number", context),
        severity=_optional_str(mapping, "severity", context),
    )


def _expected_signal_from_mapping(raw: Any, context: str) -> ExpectedPassportSignal:
    mapping = _require_mapping(raw, context)
    return ExpectedPassportSignal(
        signal_type=_require_str(mapping, "type", context),
        severity=_optional_str(mapping, "severity", context),
    )


def _require_mapping(raw: Any, context: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{context} must be an object")
    return raw


def _require_str(mapping: dict[str, Any], field: str, context: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{field} must be a non-empty string")
    return value


def _optional_str(mapping: dict[str, Any], field: str, context: str) -> str | None:
    if field not in mapping:
        return None
    value = mapping[field]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{field} must be a non-empty string")
    return value


def _optional_int(mapping: dict[str, Any], field: str, context: str) -> int | None:
    if field not in mapping or mapping[field] is None:
        return None
    value = mapping[field]
    if not isinstance(value, int):
        raise ValueError(f"{context}.{field} must be an integer")
    return value


def _optional_non_negative_int(
    mapping: dict[str, Any],
    field: str,
    context: str,
    *,
    default: int,
) -> int:
    if field not in mapping:
        return default
    value = mapping[field]
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{context}.{field} must be a non-negative integer")
    return value


def _require_str_list(
    mapping: dict[str, Any],
    field: str,
    context: str,
) -> list[str]:
    raw = mapping.get(field)
    if not isinstance(raw, list):
        raise ValueError(f"{context}.{field} must be a list")
    values: list[str] = []
    for index, value in enumerate(raw):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{context}.{field}[{index}] must be a non-empty string"
            )
        values.append(value)
    return values


def _optional_list(
    mapping: dict[str, Any],
    field: str,
    context: str,
) -> list[Any]:
    raw = mapping.get(field, [])
    if not isinstance(raw, list):
        raise ValueError(f"{context}.{field} must be a list")
    return raw


def _finding_to_dict(finding: LocalFinding) -> dict[str, Any]:
    return {
        "agent_name": finding.agent_name,
        "finding_type": finding.finding_type,
        "severity": finding.severity,
        "file_path": finding.file_path,
        "line_number": finding.line_number,
        "message": finding.message,
        "suggestion": finding.suggestion,
        "code_snippet": finding.code_snippet,
        "category": finding.category,
    }


def _expected_location(expected: ExpectedFinding) -> str:
    if expected.file_path is None:
        return ""
    if expected.line_number is None:
        return f" at {expected.file_path}"
    return f" at {expected.file_path}:{expected.line_number}"
