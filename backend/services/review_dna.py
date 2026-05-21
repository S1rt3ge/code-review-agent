"""Deterministic repository profiling for project-specific review rules."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GENERATED_BY = "review-dna-cli"


@dataclass(frozen=True)
class EvidenceSource:
    """Repository file that should influence review behavior."""

    path: str
    kind: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "kind": self.kind,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class QualityGate:
    """Local command or workflow expectation reviewers should preserve."""

    name: str
    command: str
    required: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "required": self.required,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ReviewDNAProfile:
    """Project-specific review profile generated from repository evidence."""

    project_name: str
    generated_by: str
    source_root: str
    stacks: tuple[str, ...]
    evidence_sources: tuple[EvidenceSource, ...]
    quality_gates: tuple[QualityGate, ...]
    local_constraints: tuple[str, ...]
    review_rules: tuple[str, ...]
    suggested_commands: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "generated_by": self.generated_by,
            "source_root": self.source_root,
            "stacks": list(self.stacks),
            "evidence_sources": [
                source.to_dict() for source in self.evidence_sources
            ],
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "local_constraints": list(self.local_constraints),
            "review_rules": list(self.review_rules),
            "suggested_commands": list(self.suggested_commands),
        }


@dataclass(frozen=True)
class ReviewDNACheckIssue:
    """Project-fit issue detected from changed file paths."""

    code: str
    severity: str
    message: str
    paths: tuple[str, ...]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "paths": list(self.paths),
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class ReviewDNACheckResult:
    """Advisory project-fit result for a local change set."""

    status: str
    score: int
    changed_files: tuple[str, ...]
    issues: tuple[ReviewDNACheckIssue, ...]
    recommended_commands: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "changed_files": list(self.changed_files),
            "issues": [issue.to_dict() for issue in self.issues],
            "recommended_commands": list(self.recommended_commands),
        }


@dataclass(frozen=True)
class ReviewDNACriterion:
    """Single Review Passport-ready acceptance criterion."""

    id: str
    criterion: str
    rationale: str
    evidence: tuple[str, ...]
    verification: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "criterion": self.criterion,
            "rationale": self.rationale,
            "evidence": list(self.evidence),
            "verification": list(self.verification),
        }


@dataclass(frozen=True)
class ReviewDNACriteriaPack:
    """Acceptance criteria generated from a Review DNA profile."""

    title: str
    source_profile: str
    criteria: tuple[ReviewDNACriterion, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "source_profile": self.source_profile,
            "criteria": [criterion.to_dict() for criterion in self.criteria],
        }


def build_review_dna_profile(repo_path: str | Path) -> ReviewDNAProfile:
    """Build a deterministic Review DNA profile for a local repository."""
    root = _resolve_repo_path(repo_path)
    stacks = _detect_stacks(root)
    evidence_sources = _detect_evidence_sources(root)
    quality_gates = _detect_quality_gates(root)
    local_constraints = _default_local_constraints(root)
    review_rules = _default_review_rules(root)

    return ReviewDNAProfile(
        project_name=root.name,
        generated_by=GENERATED_BY,
        source_root=".",
        stacks=tuple(stacks),
        evidence_sources=tuple(evidence_sources),
        quality_gates=tuple(quality_gates),
        local_constraints=tuple(local_constraints),
        review_rules=tuple(review_rules),
        suggested_commands=tuple(gate.command for gate in quality_gates),
    )


def render_review_dna_summary(profile: ReviewDNAProfile) -> str:
    """Render a compact terminal summary."""
    lines = [
        f"Review DNA profile for {profile.project_name}",
        f"Stacks: {', '.join(profile.stacks) if profile.stacks else 'none detected'}",
        f"Evidence sources: {len(profile.evidence_sources)}",
        f"Quality gates: {len(profile.quality_gates)}",
        "",
        "Suggested commands:",
    ]
    if profile.suggested_commands:
        lines.extend(f"- {command}" for command in profile.suggested_commands)
    else:
        lines.append("- none detected")

    return "\n".join(lines)


def render_review_dna_instructions(profile: ReviewDNAProfile) -> str:
    """Render reviewer-ready Markdown from a Review DNA profile."""
    lines = [
        "# Review DNA Instructions",
        "",
        f"Project: `{profile.project_name}`",
        "",
        "Use this profile to calibrate review comments to the repository instead of "
        "giving generic AI feedback.",
        "",
        "## Evidence",
        "",
        "Treat these files as review evidence:",
    ]

    if profile.evidence_sources:
        for source in profile.evidence_sources:
            lines.append(
                f"- `{source.path}` ({source.kind}): {source.reason}"
            )
    else:
        lines.append("- No evidence files were detected.")

    lines.extend(
        [
            "",
            "## Quality Gates",
            "",
            "Run or preserve these gates:",
        ]
    )

    if profile.quality_gates:
        for gate in profile.quality_gates:
            requirement = "required" if gate.required else "recommended"
            lines.append(
                f"- `{gate.command}` ({requirement}): {gate.reason}"
            )
    else:
        lines.append("- No quality gates were detected.")

    lines.extend(
        [
            "",
            "## Local Constraints",
            "",
        ]
    )
    lines.extend(f"- {constraint}" for constraint in profile.local_constraints)

    lines.extend(
        [
            "",
            "## Review Rules",
            "",
        ]
    )
    lines.extend(f"- {rule}" for rule in profile.review_rules)

    return "\n".join(lines)


def run_review_dna_check(
    profile: ReviewDNAProfile,
    changed_files: list[str] | tuple[str, ...],
) -> ReviewDNACheckResult:
    """Evaluate changed files against project-specific Review DNA rules."""
    normalized_paths = tuple(_normalize_changed_files(changed_files))
    issues = _build_check_issues(normalized_paths)
    score = _score_check_issues(issues)
    recommended_commands = _recommended_commands(profile, normalized_paths)
    status = _check_status(score, issues)

    return ReviewDNACheckResult(
        status=status,
        score=score,
        changed_files=normalized_paths,
        issues=tuple(issues),
        recommended_commands=tuple(recommended_commands),
    )


def render_review_dna_check_report(result: ReviewDNACheckResult) -> str:
    """Render a terminal-friendly Review DNA check report."""
    lines = [
        "Review DNA Check",
        "================",
        f"Status: {result.status}",
        f"Score: {result.score}/100",
        f"Changed files: {len(result.changed_files)}",
        "",
    ]

    if result.changed_files:
        lines.append("Files:")
        lines.extend(f"- {path}" for path in result.changed_files)
        lines.append("")

    if result.issues:
        lines.append("Issues:")
        for issue in result.issues:
            lines.append(f"- [{issue.severity}] {issue.code}: {issue.message}")
            lines.append(f"  Recommendation: {issue.recommendation}")
        lines.append("")
    else:
        lines.append("Issues: none")
        lines.append("")

    if result.recommended_commands:
        lines.append("Recommended commands:")
        lines.extend(f"- {command}" for command in result.recommended_commands)
    else:
        lines.append("Recommended commands: none")

    return "\n".join(lines)


def build_review_dna_criteria_pack(
    profile: ReviewDNAProfile,
) -> ReviewDNACriteriaPack:
    """Build stable acceptance criteria for Review Passport input."""
    evidence_paths = tuple(source.path for source in profile.evidence_sources)
    required_commands = tuple(
        gate.command for gate in profile.quality_gates if gate.required
    )
    review_eval_commands = tuple(
        command
        for command in required_commands
        if "evaluate_review_quality" in command
    )
    test_commands = tuple(
        command
        for command in required_commands
        if "pytest" in command or "npm test" in command
    )

    criteria = (
        ReviewDNACriterion(
            id="AC-1",
            criterion=(
                "Spec-first evidence exists for behavior changes, including an "
                "idea or feature spec that explains the user value, data/API "
                "impact, business logic, and edge cases."
            ),
            rationale="The project methodology requires visible evidence before implementation.",
            evidence=_filter_evidence(
                evidence_paths,
                ("README.md", "CHANGELOG.md", "SECURITY.md", "review-dna.yml"),
            ),
            verification=(),
        ),
        ReviewDNACriterion(
            id="AC-2",
            criterion=(
                "Tests cover changed behavior and keep deterministic local "
                "review flows regression-safe."
            ),
            rationale="Review DNA treats missing tests as a project-fit risk.",
            evidence=_filter_evidence(evidence_paths, ("evals/", "backend/tests/")),
            verification=test_commands,
        ),
        ReviewDNACriterion(
            id="AC-3",
            criterion=(
                "The local demo remains usable without GitHub credentials, SMTP, "
                "PostgreSQL setup outside Docker, or paid LLM providers."
            ),
            rationale="The repository promise is a no-paid-services local demo path.",
            evidence=_filter_evidence(evidence_paths, ("README.md",)),
            verification=_commands_containing(profile, ("docker compose",)),
        ),
        ReviewDNACriterion(
            id="AC-4",
            criterion=(
                "Review Passport, Anti-AI-Slop, Review DNA, and deterministic "
                "review eval behavior are preserved when review logic changes."
            ),
            rationale="The product differentiates through evidence-backed review quality.",
            evidence=_filter_evidence(
                evidence_paths,
                ("REVIEW_PASSPORT", "REVIEW_DNA", "REVIEW_EVAL", "evals/"),
            ),
            verification=review_eval_commands,
        ),
        ReviewDNACriterion(
            id="AC-5",
            criterion=(
                "Required quality gates are known and either pass locally/CI or "
                "are explicitly called out with residual risk."
            ),
            rationale="Review DNA turns repo-specific quality expectations into checks.",
            evidence=_filter_evidence(
                evidence_paths,
                ("README.md", "SECURITY.md", ".github/workflows/release.yml", ".github/CODEOWNERS"),
            ),
            verification=required_commands,
        ),
    )

    return ReviewDNACriteriaPack(
        title="Review DNA Criteria Pack",
        source_profile=profile.project_name,
        criteria=criteria,
    )


def build_review_dna_criteria_pack_for_repo(
    repo_path: str | Path,
    *,
    profile_path: str | Path | None = None,
) -> ReviewDNACriteriaPack:
    """Build Review Passport-ready criteria from a repo profile or live scan."""
    root = _resolve_repo_path(repo_path)
    candidate = Path(profile_path) if profile_path else root / "review-dna.yml"
    if not candidate.is_absolute():
        candidate = root / candidate

    profile = (
        load_review_dna_profile(candidate)
        if candidate.is_file()
        else build_review_dna_profile(root)
    )
    return build_review_dna_criteria_pack(profile)


def render_review_dna_criteria_pack(pack: ReviewDNACriteriaPack) -> str:
    """Render Review Passport-ready criteria Markdown."""
    lines = [
        "# Review DNA Criteria Pack",
        "",
        "Paste this into Review Passport as acceptance criteria.",
        "",
    ]

    for criterion in pack.criteria:
        lines.append(f"- [ ] {criterion.id}: {criterion.criterion}")
        lines.append(f"  Rationale: {criterion.rationale}")
        if criterion.evidence:
            evidence = ", ".join(f"`{path}`" for path in criterion.evidence)
            lines.append(f"  Evidence: {evidence}")
        else:
            lines.append("  Evidence: Review DNA profile")
        if criterion.verification:
            commands = ", ".join(f"`{command}`" for command in criterion.verification)
            lines.append(f"  Verification: {commands}")
        else:
            lines.append("  Verification: reviewer judgment against changed files")

    return "\n".join(lines)


def profile_to_json(profile: ReviewDNAProfile) -> str:
    """Serialize a profile to deterministic JSON."""
    return json.dumps(profile.to_dict(), indent=2, sort_keys=True) + "\n"


def review_dna_check_to_json(result: ReviewDNACheckResult) -> str:
    """Serialize a check result to deterministic JSON."""
    return json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"


def review_dna_criteria_pack_to_json(pack: ReviewDNACriteriaPack) -> str:
    """Serialize a criteria pack to deterministic JSON."""
    return json.dumps(pack.to_dict(), indent=2, sort_keys=True) + "\n"


def write_review_dna_profile(
    profile: ReviewDNAProfile,
    output_path: str | Path,
    *,
    force: bool = False,
) -> Path:
    """Write a YAML-compatible JSON profile, refusing overwrites by default."""
    path = Path(output_path)
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass --force to overwrite")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile_to_json(profile), encoding="utf-8")
    return path


def load_review_dna_profile(profile_path: str | Path) -> ReviewDNAProfile:
    """Load a profile written by `write_review_dna_profile`."""
    path = Path(profile_path)
    if not path.is_file():
        raise ValueError(f"profile path does not exist: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    return _profile_from_dict(payload)


def detect_changed_files(repo_path: str | Path) -> list[str]:
    """Read changed file paths from local git status."""
    root = _resolve_repo_path(repo_path)
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--short", "--untracked-files=normal"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "git status failed"
        raise ValueError(detail)

    paths: list[str] = []
    for raw_line in result.stdout.splitlines():
        if len(raw_line) < 4:
            continue
        path = raw_line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", maxsplit=1)[-1].strip()
        if path:
            paths.append(path.strip('"'))

    return _normalize_changed_files(paths)


def _resolve_repo_path(repo_path: str | Path) -> Path:
    root = Path(repo_path).expanduser().resolve()
    if not root.exists():
        raise ValueError(f"repo path does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"repo path is not a directory: {root}")
    return root


def _detect_stacks(root: Path) -> list[str]:
    stacks: list[str] = []
    if (root / "docker-compose.yml").is_file() or (root / "Dockerfile").is_file():
        stacks.append("docker")
    if (root / ".github" / "workflows").is_dir():
        stacks.append("github-actions")
    if (root / "backend").is_dir() or (root / "requirements.txt").is_file():
        stacks.append("python")
    if (root / "frontend" / "package.json").is_file():
        stacks.append("react-vite")
    return stacks


def _detect_evidence_sources(root: Path) -> list[EvidenceSource]:
    sources: dict[str, EvidenceSource] = {}

    for relative_path, kind, reason in [
        ("README.md", "product_overview", "Product scope and local run guidance."),
        ("CHANGELOG.md", "changelog", "Public release and change history."),
        ("SECURITY.md", "security_policy", "Security reporting and responsible disclosure policy."),
        ("review-dna.yml", "review_dna_profile", "Repository-specific review and quality profile."),
    ]:
        _add_source_if_exists(sources, root, relative_path, kind, reason)

    evals_dir = root / "evals"
    if evals_dir.is_dir():
        for path in sorted(evals_dir.glob("*.json")):
            relative_path = _relative_path(path, root)
            sources[relative_path] = EvidenceSource(
                path=relative_path,
                kind="review_eval",
                reason="Deterministic review quality regression evidence.",
            )

    return [sources[key] for key in sorted(sources)]


def _detect_quality_gates(root: Path) -> list[QualityGate]:
    gates: list[QualityGate] = []

    backend_test_command = 'python -m pytest -m "not integration" --tb=short -q'
    if (
        (root / "backend").is_dir()
        and (root / "pytest.ini").is_file()
        or _file_contains(root / "README.md", backend_test_command)
        or _file_contains(root / "AGENTS.md", backend_test_command)
    ):
        gates.append(
            QualityGate(
                name="Backend unit/API tests",
                command=backend_test_command,
                required=True,
                reason="Keeps backend behavior deterministic without integration DB.",
            )
        )

    if (root / "scripts" / "evaluate_review_quality.py").is_file():
        gates.append(
            QualityGate(
                name="Review quality evals",
                command="python scripts/evaluate_review_quality.py",
                required=True,
                reason="Proves deterministic local analyzer quality.",
            )
        )

    if (root / "backend").is_dir():
        gates.append(
            QualityGate(
                name="Backend lint",
                command="python -m ruff check backend",
                required=True,
                reason="Protects Python style and obvious correctness rules.",
            )
        )

    if (root / "frontend" / "package.json").is_file():
        gates.append(
            QualityGate(
                name="Frontend tests and build",
                command="cd frontend && npm test -- --run && npm run build",
                required=True,
                reason="Keeps the dashboard workflow buildable.",
            )
        )

    if (root / "docker-compose.yml").is_file():
        gates.append(
            QualityGate(
                name="Local stack smoke run",
                command="docker compose up --build",
                required=False,
                reason="Verifies the documented local full-stack path.",
            )
        )

    return gates


def _default_local_constraints(root: Path) -> list[str]:
    constraints = [
        "Keep the local playground usable without GitHub credentials.",
        (
            "Keep local auth usable without SMTP by supporting "
            "AUTH_REQUIRE_EMAIL_VERIFICATION=false."
        ),
        "Keep deterministic demo and eval flows usable without paid LLM providers.",
    ]
    if (root / "docker-compose.yml").is_file():
        constraints.append("Keep `docker compose up --build` as the full-stack path.")
    return constraints


def _default_review_rules(root: Path) -> list[str]:
    rules = [
        "Spec-first: new features must update an idea/spec document before code.",
        "Behavior changes need tests before implementation.",
        "Setup, public API, and workflow changes need docs updates.",
        "Local demo flows must stay usable without paid external services.",
    ]
    if (root / "backend" / "services" / "review_passport.py").is_file():
        rules.append(
            "Review logic changes should preserve Review Passport and Anti-AI-Slop evidence."
        )
    return rules


def _build_check_issues(paths: tuple[str, ...]) -> list[ReviewDNACheckIssue]:
    issues: list[ReviewDNACheckIssue] = []
    code_paths = [path for path in paths if _is_application_code_path(path)]
    local_risk_paths = [path for path in paths if _is_local_first_risk_path(path)]

    if code_paths and not any(_is_test_evidence_path(path) for path in paths):
        issues.append(
            ReviewDNACheckIssue(
                code="missing_test_evidence",
                severity="high",
                message="Application code changed without matching test evidence.",
                paths=tuple(code_paths),
                recommendation=(
                    "Add or update backend, frontend, eval, or integration tests "
                    "that prove the changed behavior."
                ),
            )
        )

    if code_paths and not any(_is_spec_or_idea_path(path) for path in paths):
        issues.append(
            ReviewDNACheckIssue(
                code="missing_spec_evidence",
                severity="high",
                message="Application code changed without spec-first evidence.",
                paths=tuple(code_paths),
                recommendation=(
                    "Update a feature spec or idea document before relying on "
                    "implementation details."
                ),
            )
        )

    has_local_first_evidence = any(
        _is_local_first_evidence_path(path) for path in paths
    )
    if local_risk_paths and not has_local_first_evidence:
        issues.append(
            ReviewDNACheckIssue(
                code="local_first_evidence",
                severity="medium",
                message="Local-first sensitive files changed without local demo evidence.",
                paths=tuple(local_risk_paths),
                recommendation=(
                    "Document or test the no-paid-services path, including "
                    "AUTH_REQUIRE_EMAIL_VERIFICATION=false when auth is affected."
                ),
            )
        )

    return issues


def _score_check_issues(issues: list[ReviewDNACheckIssue]) -> int:
    penalties = {"high": 25, "medium": 15, "low": 5}
    score = 100 - sum(penalties.get(issue.severity, 0) for issue in issues)
    return max(score, 0)


def _check_status(score: int, issues: list[ReviewDNACheckIssue]) -> str:
    if any(issue.severity == "high" for issue in issues) or score < 70:
        return "FAIL"
    if issues or score < 90:
        return "WARN"
    return "PASS"


def _recommended_commands(profile: ReviewDNAProfile, paths: tuple[str, ...]) -> list[str]:
    wanted: set[str] = set()
    if any(_is_backend_or_script_path(path) for path in paths):
        wanted.add('python -m pytest -m "not integration" --tb=short -q')
        wanted.add("python -m ruff check backend")
    if any(path.startswith("frontend/") for path in paths):
        wanted.add("cd frontend && npm test -- --run && npm run build")
    if any(_is_review_logic_path(path) for path in paths):
        wanted.add("python scripts/evaluate_review_quality.py")
    if any(_is_local_stack_path(path) for path in paths):
        wanted.add("docker compose up --build")

    ordered = [
        gate.command for gate in profile.quality_gates if gate.command in wanted
    ]
    return ordered


def _filter_evidence(paths: tuple[str, ...], prefixes_or_tokens: tuple[str, ...]) -> tuple[str, ...]:
    matches: list[str] = []
    for path in paths:
        if any(path.startswith(token) or token in path for token in prefixes_or_tokens):
            matches.append(path)
    return tuple(matches[:6])


def _commands_containing(
    profile: ReviewDNAProfile,
    tokens: tuple[str, ...],
) -> tuple[str, ...]:
    commands = [
        gate.command
        for gate in profile.quality_gates
        if any(token in gate.command for token in tokens)
    ]
    return tuple(commands)


def _normalize_changed_files(paths: list[str] | tuple[str, ...]) -> list[str]:
    normalized: set[str] = set()
    for path in paths:
        cleaned = str(path).replace("\\", "/").strip().strip('"')
        if not cleaned:
            continue
        while cleaned.startswith("./"):
            cleaned = cleaned[2:]
        if _is_generated_or_cache_path(cleaned):
            continue
        normalized.add(cleaned)
    return sorted(normalized)


def _is_generated_or_cache_path(path: str) -> bool:
    blocked_parts = {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "node_modules",
        "dist",
    }
    ignored_suffixes = (
        ".gif",
        ".ico",
        ".jpeg",
        ".jpg",
        ".pdf",
        ".png",
        ".webp",
        ".zip",
    )
    has_blocked_part = any(part in blocked_parts for part in path.split("/"))
    has_ignored_suffix = path.lower().endswith(ignored_suffixes)
    return has_blocked_part or has_ignored_suffix


def _is_application_code_path(path: str) -> bool:
    if _is_test_evidence_path(path) or _is_spec_or_idea_path(path):
        return False
    if path.startswith("backend/") and path.endswith(".py"):
        return True
    if path.startswith("frontend/src/") and _is_frontend_code_file(path):
        return True
    return path.startswith("scripts/") and path.endswith(".py")


def _is_backend_or_script_path(path: str) -> bool:
    return (
        path.startswith("backend/")
        or path.startswith("scripts/")
        or path in {"requirements.txt", "requirements.in"}
    )


def _is_frontend_code_file(path: str) -> bool:
    return path.endswith((".js", ".jsx", ".css"))


def _is_test_evidence_path(path: str) -> bool:
    name = Path(path).name.lower()
    return (
        path.startswith("backend/tests/")
        or path.startswith("evals/")
        or ".test." in name
        or ".spec." in name
        or name.startswith("test_")
    )


def _is_spec_or_idea_path(path: str) -> bool:
    return path in {"README.md", "CHANGELOG.md", "SECURITY.md", "review-dna.yml"}


def _is_local_first_risk_path(path: str) -> bool:
    lower_path = path.lower()
    risky_tokens = (
        "auth",
        "config",
        "docker",
        "email",
        "github",
        "llm",
        "notification",
        "ollama",
        "provider",
        "settings",
        "webhook",
    )
    return (
        path in {"Dockerfile", "docker-compose.yml", ".env.example"}
        or lower_path.startswith(".github/")
        or any(token in lower_path for token in risky_tokens)
    )


def _is_local_first_evidence_path(path: str) -> bool:
    lower_path = path.lower()
    return (
        path == "README.md"
        or lower_path == "readme.md"
        or "local_demo" in lower_path
        or "local-demo" in lower_path
        or "first_run" in lower_path
        or "first-run" in lower_path
    )


def _is_review_logic_path(path: str) -> bool:
    if path in {"README.md", "CHANGELOG.md", "SECURITY.md", "review-dna.yml"}:
        return False

    lower_path = path.lower()
    review_tokens = (
        "playground_review",
        "review_dna",
        "review_eval",
        "review_passport",
        "evaluate_review_quality",
    )
    return any(token in lower_path for token in review_tokens)


def _is_local_stack_path(path: str) -> bool:
    return path in {"Dockerfile", "docker-compose.yml", ".env.example"}


def _add_source_if_exists(
    sources: dict[str, EvidenceSource],
    root: Path,
    relative_path: str,
    kind: str,
    reason: str,
) -> None:
    path = root / relative_path
    if path.is_file():
        sources[relative_path] = EvidenceSource(
            path=relative_path,
            kind=kind,
            reason=reason,
        )


def _file_contains(path: Path, needle: str) -> bool:
    if not path.is_file():
        return False
    try:
        return needle in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _profile_from_dict(payload: dict[str, Any]) -> ReviewDNAProfile:
    return ReviewDNAProfile(
        project_name=str(payload["project_name"]),
        generated_by=str(payload.get("generated_by", GENERATED_BY)),
        source_root=str(payload.get("source_root", "")),
        stacks=tuple(str(item) for item in payload.get("stacks", [])),
        evidence_sources=tuple(
            EvidenceSource(
                path=str(item["path"]),
                kind=str(item["kind"]),
                reason=str(item["reason"]),
            )
            for item in payload.get("evidence_sources", [])
        ),
        quality_gates=tuple(
            QualityGate(
                name=str(item["name"]),
                command=str(item["command"]),
                required=bool(item["required"]),
                reason=str(item["reason"]),
            )
            for item in payload.get("quality_gates", [])
        ),
        local_constraints=tuple(
            str(item) for item in payload.get("local_constraints", [])
        ),
        review_rules=tuple(str(item) for item in payload.get("review_rules", [])),
        suggested_commands=tuple(
            str(item) for item in payload.get("suggested_commands", [])
        ),
    )
