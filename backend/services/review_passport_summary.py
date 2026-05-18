"""Lightweight Review Passport summaries for list views."""

from __future__ import annotations

from typing import Any


_RISK_STATUSES = {"missing", "risky", "uncertain"}


def build_review_passport_summary(passport: Any) -> dict[str, Any]:
    """Build a compact, non-sensitive Review Passport summary."""
    missing_evidence_count = len(_as_list(_read(passport, "missing_evidence", [])))
    anti_slop_signal_count = len(_as_list(_read(passport, "anti_slop_signals", [])))
    risky_criteria_count = _count_risky_criteria(
        _as_list(_read(passport, "coverage_summary", []))
    )

    verdict = str(_read(passport, "verdict", ""))
    return {
        "verdict": verdict,
        "confidence_score": _read(passport, "confidence_score", 0),
        "spec_source_type": _read(passport, "spec_source_type", ""),
        "generated_at": _read(passport, "generated_at"),
        "github_gate_state": _read(passport, "github_gate_state"),
        "readiness_reason": _build_readiness_reason(
            verdict=verdict,
            missing_evidence_count=missing_evidence_count,
            anti_slop_signal_count=anti_slop_signal_count,
            risky_criteria_count=risky_criteria_count,
            github_gate_state=_read(passport, "github_gate_state"),
        ),
        "missing_evidence_count": missing_evidence_count,
        "anti_slop_signal_count": anti_slop_signal_count,
        "risky_criteria_count": risky_criteria_count,
    }


def _build_readiness_reason(
    *,
    verdict: str,
    missing_evidence_count: int,
    anti_slop_signal_count: int,
    risky_criteria_count: int,
    github_gate_state: str | None,
) -> str:
    if verdict == "READY":
        return "Evidence covers merge criteria"

    reasons = []
    if missing_evidence_count:
        reasons.append(_pluralize(missing_evidence_count, "missing evidence item"))
    if anti_slop_signal_count:
        reasons.append(_pluralize(anti_slop_signal_count, "anti-slop signal"))
    if reasons:
        return ", ".join(reasons[:2])
    if risky_criteria_count:
        return _pluralize(risky_criteria_count, "criterion needs evidence", "criteria need evidence")
    if github_gate_state == "failure":
        return "Passport gate is failing"
    if verdict == "BLOCKED":
        return "Passport marked blocked"
    return "Review needs attention"


def _count_risky_criteria(items: list[Any]) -> int:
    return sum(
        1
        for item in items
        if str(_read(item, "status", "")).lower() in _RISK_STATUSES
    )


def _pluralize(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural or singular + 's'}"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)
