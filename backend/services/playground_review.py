"""Local playground review generation.

This module creates deterministic review results from bundled or pasted diffs.
It never calls external LLM providers and is intended for local onboarding.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.db_models import AgentExecution, Finding, Repository, Review, User

PLAYGROUND_OWNER = "local"
PLAYGROUND_REPO = "playground"
PLAYGROUND_URL = "local://playground"
LOCAL_MODEL_NAME = "local-playground"
MAX_PLAYGROUND_DIFF_CHARS = 100_000

DEMO_DIFF = """diff --git a/app/auth.py b/app/auth.py
--- a/app/auth.py
+++ b/app/auth.py
@@ -1,8 +1,14 @@
 import subprocess

+API_KEY = "sk-demo-hardcoded-secret"
+
 def authenticate(user_input, users):
+    result = eval(user_input)
     return users.get(user_input)

 async def persist_items(items, db):
+    for item in items:
+        await db.write(item)
     return True

 def load_config(path):
+    except:
+        return {}
diff --git a/app/report.py b/app/report.py
--- a/app/report.py
+++ b/app/report.py
@@ -1,4 +1,5 @@
 def render_report(payload):
+    return "Report: " + payload["title"] + " " + payload["description"] + " " + payload["notes"] + " " + payload["owner"] + " " + payload["status"]
"""

_HUNK_RE = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_SECRET_RE = re.compile(
    r"\b(api[_-]?key|secret|token|password)\b\s*=\s*['\"][^'\"]{6,}['\"]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AddedLine:
    """Single added line parsed from a unified diff."""

    file_path: str
    line_number: int
    content: str


@dataclass(frozen=True)
class LocalFinding:
    """Finding produced by deterministic local playground heuristics."""

    agent_name: str
    finding_type: str
    severity: str
    file_path: str
    line_number: int
    message: str
    suggestion: str
    code_snippet: str
    category: str

    def to_orm(self, review_id: uuid.UUID) -> Finding:
        """Convert the local finding to a database row."""
        return Finding(
            id=uuid.uuid4(),
            review_id=review_id,
            agent_name=self.agent_name,
            finding_type=self.finding_type,
            severity=self.severity,
            file_path=self.file_path,
            line_number=self.line_number,
            message=self.message,
            suggestion=self.suggestion,
            code_snippet=self.code_snippet,
            category=self.category,
        )


def validate_playground_diff(code_diff: str) -> str:
    """Validate and normalize a playground diff payload."""
    normalized = code_diff.strip()
    if not normalized:
        raise ValueError("code_diff must contain a git diff")
    if len(normalized) > MAX_PLAYGROUND_DIFF_CHARS:
        raise OverflowError("code_diff exceeds the playground size limit")
    if not _parse_added_lines(normalized):
        raise ValueError("code_diff must contain at least one added line")
    return normalized


def analyze_diff_locally(code_diff: str, selected_agents: list[str]) -> list[LocalFinding]:
    """Produce deterministic local findings from a unified diff."""
    selected = set(selected_agents)
    findings: list[LocalFinding] = []
    added_lines = _parse_added_lines(code_diff)

    for line in added_lines:
        lowered = line.content.lower()

        if "security" in selected:
            if _SECRET_RE.search(line.content):
                findings.append(
                    _finding(
                        line,
                        "security",
                        "hardcoded_secret",
                        "high",
                        "Hardcoded secret-like value detected",
                        "Move secrets to environment variables or encrypted settings.",
                    )
                )
            if "eval(" in lowered:
                findings.append(
                    _finding(
                        line,
                        "security",
                        "unsafe_eval",
                        "critical",
                        "Use of eval on dynamic input detected",
                        "Replace eval with explicit parsing or a safe command map.",
                    )
                )

        if "performance" in selected and "await " in lowered:
            if _previous_added_line_contains(added_lines, line, "for "):
                findings.append(
                    _finding(
                        line,
                        "performance",
                        "await_in_loop",
                        "medium",
                        "Await inside a loop can serialize work unnecessarily",
                        "Batch the writes or use bounded concurrency.",
                    )
                )

        if "style" in selected and len(line.content) > 120:
            findings.append(
                _finding(
                    line,
                    "style",
                    "long_line",
                    "low",
                    "Added line is difficult to scan",
                    "Split the expression into named intermediate values.",
                )
            )

        if "logic" in selected and lowered.strip() in {"except:", "catch {}", "catch { }"}:
            findings.append(
                _finding(
                    line,
                    "logic",
                    "swallowed_error",
                    "medium",
                    "Broad error handling hides failure details",
                    "Catch specific exceptions and preserve useful error context.",
                )
            )

    return findings


async def create_playground_review(
    session: AsyncSession,
    current_user: User,
    *,
    title: str,
    code_diff: str,
    selected_agents: list[str],
) -> Review:
    """Create a completed local playground review for the current user."""
    normalized_diff = validate_playground_diff(code_diff)
    repo = await _get_or_create_playground_repo(session, current_user.id)
    review_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    findings = analyze_diff_locally(normalized_diff, selected_agents)
    findings_by_agent = {
        agent: sum(1 for finding in findings if finding.agent_name == agent)
        for agent in selected_agents
    }
    tokens_input = max(1, len(normalized_diff) // 4)
    tokens_output = max(1, sum(len(finding.message) for finding in findings) // 4)

    review = Review(
        id=review_id,
        user_id=current_user.id,
        repo_id=repo.id,
        github_pr_number=await _next_playground_pr_number(session, repo.id),
        github_pr_title=title.strip() or "Local playground review",
        head_sha="local",
        base_sha="local",
        status="done",
        selected_agents=selected_agents,
        lm_used=LOCAL_MODEL_NAME,
        total_findings=len(findings),
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        estimated_cost=Decimal("0.0000"),
        completed_at=now,
    )
    session.add(review)
    await session.flush()

    session.add_all(finding.to_orm(review_id) for finding in findings)
    session.add_all(
        AgentExecution(
            id=uuid.uuid4(),
            review_id=review_id,
            agent_name=agent,
            status="done",
            started_at=now,
            completed_at=now,
            tokens_input=max(1, tokens_input // max(len(selected_agents), 1)),
            tokens_output=max(0, tokens_output // max(len(selected_agents), 1)),
            findings_count=findings_by_agent[agent],
        )
        for agent in selected_agents
    )
    await session.flush()

    result = await session.execute(
        select(Review)
        .where(Review.id == review_id)
        .options(selectinload(Review.findings), selectinload(Review.agent_executions))
    )
    return result.scalar_one()


async def _get_or_create_playground_repo(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> Repository:
    stmt = select(Repository).where(
        Repository.user_id == user_id,
        Repository.github_repo_owner == PLAYGROUND_OWNER,
        Repository.github_repo_name == PLAYGROUND_REPO,
    )
    result = await session.execute(stmt)
    repo = result.scalar_one_or_none()
    if repo is not None:
        return repo

    repo = Repository(
        id=uuid.uuid4(),
        user_id=user_id,
        github_repo_owner=PLAYGROUND_OWNER,
        github_repo_name=PLAYGROUND_REPO,
        github_repo_url=PLAYGROUND_URL,
        github_installation_id=None,
        enabled=True,
    )
    session.add(repo)
    await session.flush()
    return repo


async def _next_playground_pr_number(
    session: AsyncSession,
    repo_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.max(Review.github_pr_number)).where(Review.repo_id == repo_id)
    )
    current_max = result.scalar_one_or_none()
    return max(current_max or 999, 999) + 1


def _parse_added_lines(code_diff: str) -> list[AddedLine]:
    added: list[AddedLine] = []
    current_file = "pasted.diff"
    current_line = 1

    for raw_line in code_diff.splitlines():
        if raw_line.startswith("+++ "):
            current_file = _normalize_diff_file(raw_line[4:].strip())
            continue

        match = _HUNK_RE.search(raw_line)
        if match:
            current_line = int(match.group(1))
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            added.append(
                AddedLine(
                    file_path=current_file,
                    line_number=current_line,
                    content=raw_line[1:],
                )
            )
            current_line += 1
            continue

        if raw_line.startswith("-") and not raw_line.startswith("---"):
            continue

        if raw_line and not raw_line.startswith("diff --git"):
            current_line += 1

    return added


def _normalize_diff_file(path: str) -> str:
    if path.startswith("b/"):
        return path[2:]
    if path == "/dev/null":
        return "new-file"
    return path


def _previous_added_line_contains(
    added_lines: list[AddedLine],
    current: AddedLine,
    needle: str,
) -> bool:
    for index, line in enumerate(added_lines):
        if line is not current:
            continue
        if index == 0:
            return False
        previous = added_lines[index - 1]
        return previous.file_path == current.file_path and needle in previous.content.lower()
    return False


def _finding(
    line: AddedLine,
    agent_name: str,
    finding_type: str,
    severity: str,
    message: str,
    suggestion: str,
) -> LocalFinding:
    return LocalFinding(
        agent_name=agent_name,
        finding_type=finding_type,
        severity=severity,
        file_path=line.file_path,
        line_number=line.line_number,
        message=message,
        suggestion=suggestion,
        code_snippet=line.content.strip(),
        category="local_playground",
    )
