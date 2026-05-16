"""Deterministic repository profiling for project-specific review rules."""

from __future__ import annotations

import json
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
        source_root=str(root),
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


def profile_to_json(profile: ReviewDNAProfile) -> str:
    """Serialize a profile to deterministic JSON."""
    return json.dumps(profile.to_dict(), indent=2, sort_keys=True) + "\n"


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
        ("PROJECT_IDEA.md", "project_idea", "Spec-first product strategy."),
        ("TECHNICAL_SPEC.md", "technical_spec", "System architecture and contracts."),
        ("SPEC_TEMPLATE.md", "spec_template", "Required feature spec structure."),
    ]:
        _add_source_if_exists(sources, root, relative_path, kind, reason)

    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for path in sorted(docs_dir.glob("*.md")):
            name = path.name.lower()
            relative_path = _relative_path(path, root)
            if "spec" in name:
                sources[relative_path] = EvidenceSource(
                    path=relative_path,
                    kind="feature_spec",
                    reason="Feature-level acceptance criteria and edge cases.",
                )
            elif "idea" in name:
                sources[relative_path] = EvidenceSource(
                    path=relative_path,
                    kind="feature_idea",
                    reason="Feature-level product problem, audience, and launch plan.",
                )
            elif "checklist" in name or "policy" in name:
                sources[relative_path] = EvidenceSource(
                    path=relative_path,
                    kind="governance",
                    reason="Release, branch, or operational review policy.",
                )

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
