"""Tests for local playground review heuristics."""

import pytest

from backend.services.playground_review import analyze_diff_locally, validate_playground_diff


def test_validate_playground_diff_rejects_empty_diff() -> None:
    with pytest.raises(ValueError, match="diff"):
        validate_playground_diff("   ")


def test_validate_playground_diff_rejects_diff_without_added_lines() -> None:
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,1 @@
-print("old")
 context
"""

    with pytest.raises(ValueError, match="added"):
        validate_playground_diff(diff)


def test_analyze_diff_locally_detects_security_findings() -> None:
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,4 @@
+API_KEY = "sk-local-test"
+result = eval(user_input)
"""

    findings = analyze_diff_locally(diff, ["security"])

    assert len(findings) == 2
    assert {finding.agent_name for finding in findings} == {"security"}
    assert any("secret" in finding.message.lower() for finding in findings)
    assert any("eval" in finding.message.lower() for finding in findings)


def test_analyze_diff_locally_respects_selected_agents() -> None:
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,4 @@
+for item in items:
+    await write_item(item)
"""

    findings = analyze_diff_locally(diff, ["security"])

    assert findings == []
