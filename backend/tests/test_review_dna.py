"""Tests for Review DNA repository profiling."""

import json
from pathlib import Path

import pytest

from backend.services.review_dna import (
    build_review_dna_profile,
    render_review_dna_instructions,
    render_review_dna_check_report,
    run_review_dna_check,
    write_review_dna_profile,
)
from scripts.review_dna import main as review_dna_main


def test_build_review_dna_profile_detects_project_evidence(tmp_path: Path) -> None:
    repo = _make_review_dna_repo(tmp_path)

    profile = build_review_dna_profile(repo)

    assert profile.project_name == repo.name
    assert profile.source_root == "."
    assert profile.stacks == ("docker", "github-actions", "python", "react-vite")

    evidence_paths = {source.path for source in profile.evidence_sources}
    assert {
        "README.md",
        "PROJECT_IDEA.md",
        "TECHNICAL_SPEC.md",
        "SPEC_TEMPLATE.md",
        "docs/REVIEW_DNA_IDEA.md",
        "docs/REVIEW_PASSPORT_SPEC.md",
        "evals/review_quality_cases.json",
    }.issubset(evidence_paths)

    gate_commands = {gate.command for gate in profile.quality_gates}
    assert 'python -m pytest -m "not integration" --tb=short -q' in gate_commands
    assert "python scripts/evaluate_review_quality.py" in gate_commands
    assert "cd frontend && npm test -- --run && npm run build" in gate_commands
    assert "docker compose up --build" in gate_commands

    assert any("Spec-first" in rule for rule in profile.review_rules)
    assert any("GitHub" in constraint for constraint in profile.local_constraints)
    assert any("paid LLM" in constraint for constraint in profile.local_constraints)


def test_render_review_dna_instructions_is_reviewer_ready(tmp_path: Path) -> None:
    repo = _make_review_dna_repo(tmp_path)
    profile = build_review_dna_profile(repo)

    rendered = render_review_dna_instructions(profile)

    assert rendered.startswith("# Review DNA Instructions")
    assert "Treat these files as review evidence" in rendered
    assert "Run or preserve these gates" in rendered
    assert "python scripts/evaluate_review_quality.py" in rendered
    assert "Keep the local playground usable without GitHub credentials" in rendered


def test_write_review_dna_profile_refuses_overwrite_without_force(
    tmp_path: Path,
) -> None:
    repo = _make_review_dna_repo(tmp_path / "repo")
    profile = build_review_dna_profile(repo)
    output_path = tmp_path / "review-dna.yml"

    write_review_dna_profile(profile, output_path)

    first_payload = output_path.read_text(encoding="utf-8")
    assert '"project_name"' in first_payload
    assert '"source_root": "."' in first_payload
    assert '"quality_gates"' in first_payload

    with pytest.raises(FileExistsError, match="already exists"):
        write_review_dna_profile(profile, output_path)

    write_review_dna_profile(profile, output_path, force=True)
    assert output_path.read_text(encoding="utf-8") == first_payload


def test_review_dna_cli_scan_outputs_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_review_dna_repo(tmp_path)

    exit_code = review_dna_main(["scan", "--repo", str(repo), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["project_name"] == repo.name
    assert "react-vite" in payload["stacks"]
    assert captured.err == ""


def test_review_dna_cli_init_blocks_existing_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_review_dna_repo(tmp_path / "repo")
    output_path = tmp_path / "review-dna.yml"

    first_exit_code = review_dna_main(
        ["init", "--repo", str(repo), "--output", str(output_path)]
    )
    second_exit_code = review_dna_main(
        ["init", "--repo", str(repo), "--output", str(output_path)]
    )

    captured = capsys.readouterr()
    assert first_exit_code == 0
    assert second_exit_code == 2
    assert output_path.exists()
    assert "already exists" in captured.err


def test_review_dna_check_passes_for_docs_only_change(tmp_path: Path) -> None:
    repo = _make_review_dna_repo(tmp_path)
    profile = build_review_dna_profile(repo)

    result = run_review_dna_check(
        profile,
        changed_files=["docs/REVIEW_DNA_CLI_SPEC.md"],
    )

    assert result.status == "PASS"
    assert result.score == 100
    assert result.issues == ()
    assert result.recommended_commands == ()


def test_review_dna_check_ignores_binary_reference_assets(tmp_path: Path) -> None:
    repo = _make_review_dna_repo(tmp_path)
    profile = build_review_dna_profile(repo)

    result = run_review_dna_check(
        profile,
        changed_files=["methodology.pdf"],
    )

    assert result.status == "PASS"
    assert result.score == 100
    assert result.changed_files == ()
    assert result.issues == ()


def test_review_dna_check_flags_code_without_spec_or_tests(tmp_path: Path) -> None:
    repo = _make_review_dna_repo(tmp_path)
    profile = build_review_dna_profile(repo)

    result = run_review_dna_check(
        profile,
        changed_files=["backend/services/new_feature.py"],
    )

    assert result.status == "FAIL"
    assert result.score == 50
    assert {issue.code for issue in result.issues} == {
        "missing_spec_evidence",
        "missing_test_evidence",
    }
    assert 'python -m pytest -m "not integration" --tb=short -q' in (
        result.recommended_commands
    )
    assert "python -m ruff check backend" in result.recommended_commands


def test_review_dna_check_recommends_eval_for_review_logic_change(
    tmp_path: Path,
) -> None:
    repo = _make_review_dna_repo(tmp_path)
    profile = build_review_dna_profile(repo)

    result = run_review_dna_check(
        profile,
        changed_files=[
            "backend/services/review_dna.py",
            "backend/tests/test_review_dna.py",
            "docs/REVIEW_DNA_CLI_SPEC.md",
        ],
    )

    assert result.status == "PASS"
    assert result.score == 100
    assert result.issues == ()
    assert "python scripts/evaluate_review_quality.py" in result.recommended_commands


def test_review_dna_check_flags_local_first_risk_without_evidence(
    tmp_path: Path,
) -> None:
    repo = _make_review_dna_repo(tmp_path)
    profile = build_review_dna_profile(repo)

    result = run_review_dna_check(
        profile,
        changed_files=[
            "backend/config.py",
            "backend/tests/test_config.py",
            "docs/REVIEW_DNA_CLI_SPEC.md",
        ],
    )

    assert result.status == "WARN"
    assert result.score == 85
    assert [issue.code for issue in result.issues] == ["local_first_evidence"]
    assert "AUTH_REQUIRE_EMAIL_VERIFICATION" in result.issues[0].recommendation


def test_render_review_dna_check_report_includes_status_and_issues(
    tmp_path: Path,
) -> None:
    repo = _make_review_dna_repo(tmp_path)
    profile = build_review_dna_profile(repo)
    result = run_review_dna_check(
        profile,
        changed_files=["frontend/src/pages/NewPage.jsx"],
    )

    rendered = render_review_dna_check_report(result)

    assert "Review DNA Check" in rendered
    assert "Status: FAIL" in rendered
    assert "missing_spec_evidence" in rendered
    assert "missing_test_evidence" in rendered


def test_review_dna_cli_check_outputs_json_for_explicit_changed_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_review_dna_repo(tmp_path)

    exit_code = review_dna_main(
        [
            "check",
            "--repo",
            str(repo),
            "--changed-file",
            "backend/services/new_feature.py",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["status"] == "FAIL"
    assert payload["score"] == 50
    assert {issue["code"] for issue in payload["issues"]} == {
        "missing_spec_evidence",
        "missing_test_evidence",
    }
    assert captured.err == ""


def test_review_dna_cli_check_advisory_returns_success_for_project_fit_fail(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_review_dna_repo(tmp_path)

    exit_code = review_dna_main(
        [
            "check",
            "--repo",
            str(repo),
            "--changed-file",
            "backend/services/new_feature.py",
            "--json",
            "--advisory",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "FAIL"
    assert payload["score"] == 50
    assert captured.err == ""


def test_review_dna_workflow_is_advisory() -> None:
    workflow_path = Path(".github/workflows/review-dna.yml")

    workflow = workflow_path.read_text(encoding="utf-8")

    assert "Review DNA Advisory Check" in workflow
    assert "pull_request:" in workflow
    assert "python scripts/review_dna.py check --advisory --json" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "review-dna-check.json" in workflow
    assert "gh pr comment" not in workflow


def _make_review_dna_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
    (path / "PROJECT_IDEA.md").write_text("# Idea\n", encoding="utf-8")
    (path / "TECHNICAL_SPEC.md").write_text("# Technical Spec\n", encoding="utf-8")
    (path / "SPEC_TEMPLATE.md").write_text("# Spec Template\n", encoding="utf-8")
    (path / "AGENTS.md").write_text(
        "# Agent Rules\n"
        'python -m pytest -m "not integration" --tb=short -q\n',
        encoding="utf-8",
    )
    (path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (path / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")

    docs_dir = path / "docs"
    docs_dir.mkdir()
    (docs_dir / "REVIEW_DNA_IDEA.md").write_text(
        "# Review DNA Idea\n",
        encoding="utf-8",
    )
    (docs_dir / "REVIEW_PASSPORT_SPEC.md").write_text(
        "# Review Passport Spec\n",
        encoding="utf-8",
    )
    (docs_dir / "branch-protection-policy.md").write_text(
        "# Branch Protection\n",
        encoding="utf-8",
    )

    evals_dir = path / "evals"
    evals_dir.mkdir()
    (evals_dir / "review_quality_cases.json").write_text(
        '{"cases": []}\n',
        encoding="utf-8",
    )

    scripts_dir = path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "evaluate_review_quality.py").write_text(
        'print("ok")\n',
        encoding="utf-8",
    )

    frontend_dir = path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "package.json").write_text('{"scripts": {}}\n', encoding="utf-8")

    github_workflows_dir = path / ".github" / "workflows"
    github_workflows_dir.mkdir(parents=True)
    (github_workflows_dir / "ci.yml").write_text("name: CI\n", encoding="utf-8")

    backend_dir = path / "backend"
    backend_dir.mkdir()
    return path
