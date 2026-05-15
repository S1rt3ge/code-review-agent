"""Tests for deterministic Review Passport generation."""

from backend.services.review_passport import (
    build_review_passport,
    detect_anti_slop_signals,
    extract_acceptance_criteria,
    snapshot_diff,
)


def test_extract_acceptance_criteria_from_markdown_checklist() -> None:
    spec = """
    Acceptance criteria:
    - User can run the local demo without paid providers.
    - Webhook setup must show free tunnel commands.
    - No SMTP provider is required for local login.
    """

    criteria = extract_acceptance_criteria(spec)

    assert [item["id"] for item in criteria] == ["AC-1", "AC-2", "AC-3"]
    assert criteria[0]["criterion"] == "User can run the local demo without paid providers."
    assert "free tunnel" in criteria[1]["criterion"]


def test_snapshot_diff_limits_added_lines_and_changed_files() -> None:
    diff = """diff --git a/frontend/src/App.jsx b/frontend/src/App.jsx
--- a/frontend/src/App.jsx
+++ b/frontend/src/App.jsx
@@ -1,2 +1,4 @@
+export function App() {
+  return <main>Demo</main>
+}
"""

    snapshot = snapshot_diff(diff)

    assert snapshot["changed_files"] == ["frontend/src/App.jsx"]
    assert snapshot["added_lines"][0]["line_number"] == 1
    assert snapshot["added_lines"][0]["content"] == "export function App() {"


def test_detect_anti_slop_signals_flags_missing_tests_and_placeholders() -> None:
    changed_files = ["backend/services/review_passport.py", "frontend/src/pages/ReviewDetail.jsx"]
    added_lines = [
        {
            "file_path": "backend/services/review_passport.py",
            "line_number": 12,
            "content": "raise NotImplementedError('later')",
        },
        {
            "file_path": "frontend/src/pages/ReviewDetail.jsx",
            "line_number": 44,
            "content": "return null",
        },
    ]

    signals = detect_anti_slop_signals(changed_files, added_lines)

    assert {signal["type"] for signal in signals} >= {
        "missing_tests",
        "placeholder_code",
    }
    assert any(signal["severity"] == "high" for signal in signals)


def test_build_review_passport_blocks_when_required_criteria_are_missing() -> None:
    spec = """
    - User can run local demo in 5 minutes.
    - Password reset must send a verification email.
    """
    diff = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
+Run the local demo with docker compose up --build.
"""
    snapshot = snapshot_diff(diff)

    passport = build_review_passport(
        mode="combined",
        spec_source_type="manual",
        spec_source_ref="Issue #53",
        spec_input=spec,
        findings=[],
        changed_files=snapshot["changed_files"],
        added_lines=snapshot["added_lines"],
    )

    statuses = {item["criterion_id"]: item["status"] for item in passport["coverage_summary"]}
    assert statuses["AC-1"] == "covered"
    assert statuses["AC-2"] == "missing"
    assert passport["verdict"] == "READY_WITH_RISKS"
    assert passport["confidence_score"] < 100


def test_build_review_passport_ready_when_all_criteria_have_evidence() -> None:
    spec = """
    - User can run local demo with docker compose.
    - Review detail shows passport verdict.
    """
    diff = """diff --git a/frontend/src/pages/ReviewDetail.jsx b/frontend/src/pages/ReviewDetail.jsx
--- a/frontend/src/pages/ReviewDetail.jsx
+++ b/frontend/src/pages/ReviewDetail.jsx
@@ -1,2 +1,5 @@
+const verdict = 'READY'
+const copy = 'Run local demo with docker compose and show passport verdict.'
diff --git a/frontend/src/pages/__tests__/ReviewDetail.test.jsx b/frontend/src/pages/__tests__/ReviewDetail.test.jsx
--- a/frontend/src/pages/__tests__/ReviewDetail.test.jsx
+++ b/frontend/src/pages/__tests__/ReviewDetail.test.jsx
@@ -1,2 +1,4 @@
+test('shows passport verdict', () => {
+  expect(verdict).toBe('READY')
+})
"""
    snapshot = snapshot_diff(diff)

    passport = build_review_passport(
        mode="combined",
        spec_source_type="manual",
        spec_source_ref=None,
        spec_input=spec,
        findings=[],
        changed_files=snapshot["changed_files"],
        added_lines=snapshot["added_lines"],
    )

    assert passport["verdict"] == "READY"
    assert passport["missing_evidence"] == []
    assert passport["qa_steps"][0]["command"] == "docker compose up --build"
