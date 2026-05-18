"""Deterministic Review Passport generation.

The first passport implementation is intentionally local-only. It uses the
stored review findings plus a normalized diff snapshot to produce spec coverage,
anti-slop signals, a QA script, and a merge verdict without sending user code to
external providers.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db_models import Review, ReviewInputSnapshot, ReviewPassport, User
from backend.services.playground_review import _parse_added_lines, validate_playground_diff


VALID_PASSPORT_MODES = {"spec_evidence", "anti_ai_slop", "combined"}
VALID_SPEC_SOURCE_TYPES = {
    "manual",
    "local_demo",
    "pr_body",
    "github_issue",
    "review_dna",
}
MAX_SPEC_CHARS = 20_000
MAX_CRITERIA = 25
MAX_SNAPSHOT_ADDED_LINES = 2_500
MAX_SNAPSHOT_LINE_CHARS = 500

_CRITERION_PREFIX_RE = re.compile(r"^\s*(?:[-*]\s+(?:\[[ xX]\]\s*)?|\d+[\.)]\s+)")
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]{2,}")
_TEST_DECL_RE = re.compile(r"\b(it|test|describe)\s*\(|\bdef\s+test_[A-Za-z0-9_]*\s*\(")
_ASSERTION_RE = re.compile(r"\b(assert|expect|toBe|toEqual|toHaveBeen|pytest\.raises)\b")
_MOCK_RE = re.compile(r"\b(mock[A-Za-z0-9_]*|patch|MagicMock|AsyncMock|vi\.fn|jest\.fn)\b")

_STOPWORDS = {
    "and",
    "are",
    "can",
    "for",
    "from",
    "has",
    "have",
    "into",
    "must",
    "not",
    "required",
    "should",
    "that",
    "the",
    "this",
    "user",
    "with",
    "without",
}

_APP_EXTENSIONS = (".py", ".js", ".jsx", ".ts", ".tsx")


def extract_acceptance_criteria(spec_input: str) -> list[dict[str, str]]:
    """Extract deterministic acceptance criteria from pasted spec text."""
    criteria: list[dict[str, str]] = []
    for raw_line in spec_input.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        is_prefixed = bool(_CRITERION_PREFIX_RE.match(line))
        lowered = line.lower()
        has_keyword = any(
            keyword in lowered
            for keyword in ("acceptance", "user can", "must", "should", "no paid")
        )
        if not is_prefixed and not has_keyword:
            continue

        normalized = _CRITERION_PREFIX_RE.sub("", line)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if normalized.endswith(":") or len(normalized) < 12:
            continue
        criteria.append(
            {
                "id": f"AC-{len(criteria) + 1}",
                "criterion": normalized[:240],
            }
        )
        if len(criteria) >= MAX_CRITERIA:
            break
    return criteria


def snapshot_diff(code_diff: str) -> dict[str, list[Any]]:
    """Validate a unified diff and return the stored snapshot shape."""
    normalized = validate_playground_diff(code_diff)
    added_lines = _parse_added_lines(normalized)
    changed_files = sorted({line.file_path for line in added_lines})
    return {
        "changed_files": changed_files,
        "added_lines": [
            {
                "file_path": line.file_path,
                "line_number": line.line_number,
                "content": line.content.strip()[:MAX_SNAPSHOT_LINE_CHARS],
            }
            for line in added_lines[:MAX_SNAPSHOT_ADDED_LINES]
        ],
    }


def detect_anti_slop_signals(
    changed_files: list[str],
    added_lines: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect deterministic AI-generated-code risk patterns."""
    signals: list[dict[str, Any]] = []
    test_files = [path for path in changed_files if _is_test_file(path)]
    app_files = [
        path
        for path in changed_files
        if not _is_test_file(path) and path.endswith(_APP_EXTENSIONS)
    ]

    if app_files and not test_files:
        signals.append(
            _signal(
                "missing_tests",
                "medium",
                "Application code changed without matching test changes",
                app_files[:8],
                "Add focused tests for the changed application behavior.",
            )
        )

    placeholder_evidence = [
        _line_ref(line)
        for line in added_lines
        if _looks_like_placeholder(str(line.get("content", "")))
    ]
    if placeholder_evidence:
        signals.append(
            _signal(
                "placeholder_code",
                "high",
                "Placeholder or fake-complete code was added",
                placeholder_evidence[:8],
                "Replace placeholders with real behavior before treating the PR as done.",
            )
        )

    swallowed_error_evidence = [
        _line_ref(line)
        for line in added_lines
        if _swallows_errors(str(line.get("content", "")))
    ]
    if swallowed_error_evidence:
        signals.append(
            _signal(
                "swallowed_error",
                "medium",
                "Error handling hides failures without useful recovery",
                swallowed_error_evidence[:8],
                "Catch specific errors and preserve actionable context.",
            )
        )

    if len(changed_files) > 12 or len({_top_level(path) for path in changed_files}) > 5:
        signals.append(
            _signal(
                "broad_blast_radius",
                "medium",
                "The change spans a broad set of files or directories",
                changed_files[:10],
                "Split unrelated changes or add stronger evidence for the whole surface.",
            )
        )

    assertionless_evidence: list[str] = []
    mock_lines = 0
    assertion_lines = 0
    for line in added_lines:
        content = str(line.get("content", ""))
        if _is_test_file(str(line.get("file_path", ""))):
            if _TEST_DECL_RE.search(content):
                assertionless_evidence.append(_line_ref(line))
            if _ASSERTION_RE.search(content):
                assertion_lines += 1
                assertionless_evidence.clear()
            if _MOCK_RE.search(content):
                mock_lines += 1

    if assertionless_evidence:
        signals.append(
            _signal(
                "assertionless_tests",
                "medium",
                "Tests were added without visible assertions",
                assertionless_evidence[:8],
                "Assert user-visible behavior or important state transitions.",
            )
        )

    if mock_lines > 3 and mock_lines > assertion_lines * 3:
        signals.append(
            _signal(
                "over_mocked_tests",
                "medium",
                "Mock setup dominates the added test evidence",
                test_files[:8],
                "Prefer behavior-focused tests with fewer implementation mocks.",
            )
        )

    unbounded_evidence = [
        _line_ref(line)
        for line in added_lines
        if _looks_like_unbounded_input(str(line.get("content", "")))
    ]
    if unbounded_evidence:
        signals.append(
            _signal(
                "unbounded_input",
                "medium",
                "User input path appears to lack an explicit size limit",
                unbounded_evidence[:8],
                "Add max length or payload size validation at the API boundary.",
            )
        )

    return signals


def build_review_passport(
    *,
    mode: str,
    spec_source_type: str,
    spec_source_ref: str | None,
    spec_input: str | None,
    findings: list[Any],
    changed_files: list[str],
    added_lines: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the deterministic Review Passport response payload."""
    normalized_mode = _validate_mode(mode)
    normalized_source_type = _validate_source_type(spec_source_type)
    normalized_spec = (spec_input or "").strip()
    if len(normalized_spec) > MAX_SPEC_CHARS:
        raise OverflowError("spec_input exceeds the passport size limit")

    criteria = extract_acceptance_criteria(normalized_spec)
    criteria_truncated = _criteria_were_truncated(normalized_spec, criteria)
    anti_slop_signals = (
        detect_anti_slop_signals(changed_files, added_lines)
        if normalized_mode in {"anti_ai_slop", "combined"}
        else []
    )
    if criteria_truncated:
        anti_slop_signals.append(
            _signal(
                "criteria_truncated",
                "low",
                "Only the first 25 acceptance criteria were evaluated",
                [],
                "Split large specs into smaller review slices.",
            )
        )

    if normalized_mode in {"spec_evidence", "combined"} and not criteria:
        verdict = "BLOCKED"
        coverage_summary: list[dict[str, Any]] = []
        missing_evidence = [
            {
                "criterion_id": "AC-0",
                "criterion": "No acceptance criteria could be extracted",
                "reason": "Paste bullet, checklist, or numbered acceptance criteria.",
            }
        ]
    else:
        coverage_summary = _build_coverage(criteria, findings, changed_files, added_lines)
        missing_evidence = [
            {
                "criterion_id": item["criterion_id"],
                "criterion": item["criterion"],
                "reason": "No direct file, line, or finding evidence matched this criterion.",
            }
            for item in coverage_summary
            if item["status"] == "missing"
        ]
        verdict = _calculate_verdict(coverage_summary, findings, anti_slop_signals)

    confidence_score = _calculate_confidence(
        coverage_summary,
        findings,
        anti_slop_signals,
        blocked=verdict == "BLOCKED",
    )

    return {
        "mode": normalized_mode,
        "spec_source_type": normalized_source_type,
        "spec_source_ref": spec_source_ref.strip()[:120] if spec_source_ref else None,
        "spec_input": normalized_spec or None,
        "spec_digest": _digest(normalized_spec),
        "verdict": verdict,
        "confidence_score": confidence_score,
        "coverage_summary": coverage_summary,
        "anti_slop_signals": anti_slop_signals,
        "qa_steps": _generate_qa_steps(coverage_summary, anti_slop_signals, changed_files),
        "missing_evidence": missing_evidence,
    }


async def create_or_replace_review_passport(
    session: AsyncSession,
    *,
    review: Review,
    current_user: User,
    mode: str,
    spec_source_type: str,
    spec_source_ref: str | None,
    spec_input: str | None,
    code_diff: str | None,
) -> ReviewPassport:
    """Create or replace the persisted passport for an owned review."""
    snapshot = await _get_or_create_diff_snapshot(
        session,
        review=review,
        current_user=current_user,
        code_diff=code_diff,
    )
    report = build_review_passport(
        mode=mode,
        spec_source_type=spec_source_type,
        spec_source_ref=spec_source_ref,
        spec_input=spec_input,
        findings=list(review.findings or []),
        changed_files=list(snapshot.changed_files or []),
        added_lines=list(snapshot.added_lines or []),
    )

    existing = await get_review_passport(session, review.id, current_user.id)
    now = datetime.now(timezone.utc)
    if existing is None:
        passport = ReviewPassport(
            id=uuid.uuid4(),
            review_id=review.id,
            user_id=current_user.id,
            created_at=now,
        )
        session.add(passport)
    else:
        passport = existing

    passport.mode = report["mode"]
    passport.spec_source_type = report["spec_source_type"]
    passport.spec_source_ref = report["spec_source_ref"]
    passport.spec_input = report["spec_input"]
    passport.spec_digest = report["spec_digest"]
    passport.verdict = report["verdict"]
    passport.confidence_score = report["confidence_score"]
    passport.coverage_summary = report["coverage_summary"]
    passport.anti_slop_signals = report["anti_slop_signals"]
    passport.qa_steps = report["qa_steps"]
    passport.missing_evidence = report["missing_evidence"]
    passport.generated_at = now
    passport.updated_at = now

    await session.flush()
    await session.refresh(passport)
    return passport


async def get_review_passport(
    session: AsyncSession,
    review_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ReviewPassport | None:
    """Return the owned passport for a review, if present."""
    result = await session.execute(
        select(ReviewPassport).where(
            ReviewPassport.review_id == review_id,
            ReviewPassport.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_review_passport(
    session: AsyncSession,
    review_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Delete an owned passport and return whether one existed."""
    passport = await get_review_passport(session, review_id, user_id)
    if passport is None:
        return False
    await session.delete(passport)
    await session.flush()
    return True


async def _get_or_create_diff_snapshot(
    session: AsyncSession,
    *,
    review: Review,
    current_user: User,
    code_diff: str | None,
) -> ReviewInputSnapshot:
    result = await session.execute(
        select(ReviewInputSnapshot).where(
            ReviewInputSnapshot.review_id == review.id,
            ReviewInputSnapshot.user_id == current_user.id,
            ReviewInputSnapshot.input_type == "diff",
        )
    )
    snapshot = result.scalar_one_or_none()
    if code_diff is None:
        if snapshot is None:
            raise ValueError("code_diff is required until a diff snapshot exists")
        return snapshot

    snapshot_payload = snapshot_diff(code_diff)
    digest = _digest(code_diff.strip())
    if snapshot is None:
        snapshot = ReviewInputSnapshot(
            id=uuid.uuid4(),
            review_id=review.id,
            user_id=current_user.id,
            input_type="diff",
        )
        session.add(snapshot)

    snapshot.content_digest = digest
    snapshot.changed_files = snapshot_payload["changed_files"]
    snapshot.added_lines = snapshot_payload["added_lines"]
    await session.flush()
    return snapshot


def _build_coverage(
    criteria: list[dict[str, str]],
    findings: list[Any],
    changed_files: list[str],
    added_lines: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coverage: list[dict[str, Any]] = []
    finding_items = [_finding_to_dict(finding) for finding in findings]

    for criterion in criteria:
        tokens = _tokens(criterion["criterion"])
        evidence = _match_evidence(tokens, finding_items, changed_files, added_lines)
        risky = any(
            item["type"] == "finding"
            and str(item.get("severity", "")).lower() in {"high", "critical"}
            for item in evidence
        )
        if risky:
            status = "risky"
        elif any(item["type"] in {"file_line", "changed_file", "finding"} for item in evidence):
            status = "covered"
        elif evidence:
            status = "uncertain"
        else:
            status = "missing"

        coverage.append(
            {
                "criterion_id": criterion["id"],
                "criterion": criterion["criterion"],
                "status": status,
                "evidence": evidence[:5],
            }
        )
    return coverage


def _match_evidence(
    tokens: set[str],
    findings: list[dict[str, Any]],
    changed_files: list[str],
    added_lines: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if not tokens:
        return evidence

    for line in added_lines:
        overlap = tokens & _tokens(str(line.get("content", "")))
        if _strong_overlap(tokens, overlap):
            evidence.append(
                {
                    "type": "file_line",
                    "file_path": line.get("file_path"),
                    "line_number": line.get("line_number"),
                    "summary": "Added line matches the acceptance criterion.",
                }
            )
            break

    for path in changed_files:
        overlap = tokens & _tokens(path.replace("/", " ").replace("_", " "))
        if _strong_overlap(tokens, overlap):
            evidence.append(
                {
                    "type": "changed_file",
                    "file_path": path,
                    "summary": "Changed file path matches the acceptance criterion.",
                }
            )
            break

    for finding in findings:
        corpus = " ".join(
            str(finding.get(field, ""))
            for field in ("message", "suggestion", "finding_type", "file_path")
        )
        overlap = tokens & _tokens(corpus)
        if _strong_overlap(tokens, overlap):
            evidence.append(
                {
                    "type": "finding",
                    "finding_id": str(finding.get("id", "")) or None,
                    "file_path": finding.get("file_path"),
                    "line_number": finding.get("line_number"),
                    "severity": finding.get("severity"),
                    "summary": str(finding.get("message", "Finding matches criterion"))[
                        :300
                    ],
                }
            )
            break

    if not evidence:
        weak_overlap = set()
        for line in added_lines:
            weak_overlap |= tokens & _tokens(str(line.get("content", "")))
        if weak_overlap:
            evidence.append(
                {
                    "type": "inference",
                    "summary": "Weak textual overlap exists, but no direct file-line evidence was strong enough.",
                }
            )

    return evidence


def _calculate_verdict(
    coverage_summary: list[dict[str, Any]],
    findings: list[Any],
    anti_slop_signals: list[dict[str, Any]],
) -> str:
    severities = {str(_get(finding, "severity", "")).lower() for finding in findings}
    signal_severities = {str(signal.get("severity", "")).lower() for signal in anti_slop_signals}
    statuses = {item["status"] for item in coverage_summary}

    if "critical" in severities:
        return "BLOCKED"
    if "missing" in statuses and signal_severities & {"high", "critical"}:
        return "BLOCKED"
    if statuses & {"missing", "risky", "uncertain"}:
        return "READY_WITH_RISKS"
    if severities & {"medium", "high", "critical"}:
        return "READY_WITH_RISKS"
    if signal_severities & {"medium", "high", "critical"}:
        return "READY_WITH_RISKS"
    return "READY"


def _calculate_confidence(
    coverage_summary: list[dict[str, Any]],
    findings: list[Any],
    anti_slop_signals: list[dict[str, Any]],
    *,
    blocked: bool,
) -> int:
    score = 60 if blocked and not coverage_summary else 100
    for item in coverage_summary:
        if item["status"] == "missing":
            score -= 20
        elif item["status"] == "risky":
            score -= 12
        elif item["status"] == "uncertain":
            score -= 8
    for finding in findings:
        severity = str(_get(finding, "severity", "")).lower()
        if severity == "critical":
            score -= 25
        elif severity == "high":
            score -= 15
    for signal in anti_slop_signals:
        severity = str(signal.get("severity", "")).lower()
        if severity in {"critical", "high"}:
            score -= 15
        elif severity == "medium":
            score -= 8
    return max(0, min(100, score))


def _generate_qa_steps(
    coverage_summary: list[dict[str, Any]],
    anti_slop_signals: list[dict[str, Any]],
    changed_files: list[str],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = [
        {
            "step": 1,
            "title": "Run local stack",
            "command": "docker compose up --build",
            "expected": "Frontend is available at http://localhost:5173",
        },
        {
            "step": 2,
            "title": "Open the dashboard",
            "command": None,
            "expected": "You can register or log in with local email verification disabled.",
        },
        {
            "step": 3,
            "title": "Open the reviewed change",
            "command": None,
            "expected": "The review detail page shows findings and the passport verdict.",
        },
    ]

    for item in coverage_summary[:5]:
        if item["status"] in {"covered", "risky", "uncertain"}:
            steps.append(
                {
                    "step": len(steps) + 1,
                    "title": f"Verify {item['criterion_id']}",
                    "command": None,
                    "expected": item["criterion"],
                }
            )

    signal_types = {signal["type"] for signal in anti_slop_signals}
    if "missing_tests" in signal_types:
        steps.append(
            {
                "step": len(steps) + 1,
                "title": "Run focused tests",
                "command": _test_command_for_files(changed_files),
                "expected": "Tests cover the changed application behavior.",
            }
        )
    if "placeholder_code" in signal_types:
        steps.append(
            {
                "step": len(steps) + 1,
                "title": "Inspect placeholder evidence",
                "command": None,
                "expected": "No placeholder path executes in the completed workflow.",
            }
        )

    return steps


def _test_command_for_files(changed_files: list[str]) -> str:
    if any(path.startswith("frontend/") for path in changed_files):
        return "cd frontend && npm test -- --run"
    return 'python -m pytest -m "not integration" --tb=short -q'


def _validate_mode(mode: str) -> str:
    normalized = mode.strip()
    if normalized not in VALID_PASSPORT_MODES:
        raise ValueError("Invalid passport mode")
    return normalized


def _validate_source_type(source_type: str) -> str:
    normalized = source_type.strip()
    if normalized not in VALID_SPEC_SOURCE_TYPES:
        raise ValueError("Invalid passport source type")
    return normalized


def _criteria_were_truncated(
    spec_input: str,
    extracted: list[dict[str, str]],
) -> bool:
    if len(extracted) < MAX_CRITERIA:
        return False
    return len(extract_acceptance_criteria_without_limit(spec_input)) > MAX_CRITERIA


def extract_acceptance_criteria_without_limit(spec_input: str) -> list[dict[str, str]]:
    """Extract criteria without the public 25-item cap for truncation checks."""
    criteria: list[dict[str, str]] = []
    for raw_line in spec_input.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        is_prefixed = bool(_CRITERION_PREFIX_RE.match(line))
        lowered = line.lower()
        has_keyword = any(
            keyword in lowered
            for keyword in ("acceptance", "user can", "must", "should", "no paid")
        )
        if not is_prefixed and not has_keyword:
            continue
        normalized = _CRITERION_PREFIX_RE.sub("", line)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if normalized.endswith(":") or len(normalized) < 12:
            continue
        criteria.append({"id": f"AC-{len(criteria) + 1}", "criterion": normalized[:240]})
    return criteria


def _signal(
    signal_type: str,
    severity: str,
    summary: str,
    evidence: list[str],
    suggestion: str,
) -> dict[str, Any]:
    return {
        "type": signal_type,
        "severity": severity,
        "summary": summary,
        "evidence": evidence,
        "suggestion": suggestion,
    }


def _looks_like_placeholder(content: str) -> bool:
    lowered = content.strip().lower()
    return (
        "todo" in lowered
        or "fixme" in lowered
        or "notimplementederror" in lowered
        or lowered in {"pass", "return null", "return none"}
        or "placeholder" in lowered
    )


def _swallows_errors(content: str) -> bool:
    lowered = content.strip().lower()
    return (
        lowered in {"except:", "catch {}", "catch { }"}
        or "except exception" in lowered
    )


def _looks_like_unbounded_input(content: str) -> bool:
    lowered = content.lower()
    accepts_text = "textarea" in lowered or "code_diff" in lowered or "spec_input" in lowered
    has_limit = any(token in lowered for token in ("max_length", "maxlength", "limit", "413"))
    return accepts_text and not has_limit


def _is_test_file(path: str) -> bool:
    lowered = path.lower()
    return (
        "__tests__" in lowered
        or "/tests/" in lowered
        or "\\tests\\" in lowered
        or lowered.endswith((".test.js", ".test.jsx", ".test.ts", ".test.tsx", "_test.py"))
        or ".spec." in lowered
        or lowered.startswith("backend/tests/")
    )


def _top_level(path: str) -> str:
    return path.replace("\\", "/").split("/", 1)[0]


def _line_ref(line: dict[str, Any]) -> str:
    return f"{line.get('file_path')}:{line.get('line_number')}"


def _tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in _WORD_RE.findall(value.replace("_", " "))
        if token.lower() not in _STOPWORDS
    }


def _strong_overlap(tokens: set[str], overlap: set[str]) -> bool:
    if not overlap:
        return False
    if len(tokens) <= 2:
        return len(overlap) >= 1
    return len(overlap) >= 2 or len(overlap) / max(len(tokens), 1) >= 0.5


def _finding_to_dict(finding: Any) -> dict[str, Any]:
    return {
        "id": _get(finding, "id"),
        "message": _get(finding, "message", ""),
        "suggestion": _get(finding, "suggestion", ""),
        "finding_type": _get(finding, "finding_type", ""),
        "file_path": _get(finding, "file_path", ""),
        "line_number": _get(finding, "line_number"),
        "severity": _get(finding, "severity", ""),
    }


def _get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
