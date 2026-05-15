"""Review Passport merge gate mapping."""

from __future__ import annotations

from typing import Any


GITHUB_STATUS_CONTEXT = "AI Review Passport Gate"

_GATE_BY_VERDICT = {
    "READY": {
        "state": "success",
        "description": "Review Passport READY: evidence covers merge criteria.",
        "required_action": "merge_ready",
    },
    "READY_WITH_RISKS": {
        "state": "failure",
        "description": "Review Passport READY_WITH_RISKS: review required before merge.",
        "required_action": "review_risks",
    },
    "BLOCKED": {
        "state": "failure",
        "description": "Review Passport BLOCKED: missing required evidence.",
        "required_action": "fix_blockers",
    },
}

_UNKNOWN_GATE = {
    "state": "error",
    "description": "Review Passport gate could not map the current verdict.",
    "required_action": "investigate_gate",
}


def build_passport_gate(passport: Any) -> dict[str, Any]:
    """Build the GitHub commit status payload for a Review Passport."""
    verdict = str(_read(passport, "verdict", "UNKNOWN"))
    gate = _GATE_BY_VERDICT.get(verdict, _UNKNOWN_GATE)
    return {
        "context": GITHUB_STATUS_CONTEXT,
        "verdict": verdict,
        "state": gate["state"],
        "description": gate["description"],
        "required_action": gate["required_action"],
        "github_gate_state": _read(passport, "github_gate_state"),
        "github_gate_url": _read(passport, "github_gate_url"),
        "github_gate_posted_at": _read(passport, "github_gate_posted_at"),
    }


def _read(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)
