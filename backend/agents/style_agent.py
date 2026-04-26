"""Code style analysis agent.

Analyses code chunks for style violations including naming conventions,
line length, import organisation, missing docstrings, and dead code.

Uses a cheaper model tier (Sonnet) since style checks don't require
deep reasoning.

Functions:
    run: Analyse a list of CodeChunk objects and return style findings.
"""

import json
import logging
from typing import Any, Awaitable, Callable

from backend.agents.llm_router import LLMConfig
from backend.agents.orchestrator import MAX_CODE_CHARS
from backend.services.code_extractor import CodeChunk

logger = logging.getLogger(__name__)

CATEGORY = "style"

_PROMPT_TEMPLATE = """\
You are a code style reviewer. Analyse the following {language} code \
for style and maintainability issues.

File: {filename}
Lines {start_line}–{end_line}:

```{language}
{code}
```

Focus ONLY on concrete style violations in the ADDED/CHANGED lines, not on \
pre-existing code that wasn't modified:
- Naming conventions (snake_case for Python vars/funcs, PascalCase for classes, \
  camelCase for JS/TS)
- Lines exceeding 120 characters
- Missing or inadequate docstrings/JSDoc on public functions and classes
- Unused imports or variables
- Magic numbers/strings that should be named constants
- Overly complex functions (too many responsibilities, deep nesting >4 levels)
- Inconsistent return types or missing type hints on public APIs (Python/TS)
- TODO/FIXME/HACK comments left in production code

Return ONLY valid JSON. Do not include any text outside the JSON object.

{{
    "findings": [
        {{
            "finding_type": "missing_docstring",
            "severity": "low",
            "line_number": 42,
            "message": "Concise human-readable description of the issue",
            "suggestion": "Specific, actionable fix recommendation",
            "code_snippet": "offending line(s) of code (max 3 lines)"
        }}
    ]
}}

Severity levels: medium (reduces readability significantly or violates project \
standards), low (minor style issue), info (suggestion only).

Only report issues that are clear violations. Do not flag subjective preferences.
If you find no style issues, return: {{"findings": []}}
"""


def _build_prompt(chunk: CodeChunk) -> str:
    code = chunk.content[:MAX_CODE_CHARS]
    return _PROMPT_TEMPLATE.format(
        language=chunk.language,
        filename=chunk.filename,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        code=code,
    )


def _parse_findings(raw: str, chunk: CodeChunk) -> list[dict]:
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(
            line for line in lines if not line.startswith("```")
        ).strip()

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        logger.warning("style_agent: could not parse JSON for %s", chunk.filename)
        return []

    raw_findings = data.get("findings", [])
    if not isinstance(raw_findings, list):
        return []

    VALID_SEVERITIES = {"medium", "low", "info"}
    validated: list[dict] = []

    for f in raw_findings:
        if not isinstance(f, dict):
            continue
        if not all(k in f for k in ("finding_type", "severity", "line_number", "message")):
            continue
        if f["severity"] not in VALID_SEVERITIES:
            continue

        validated.append(
            {
                "agent_name": "style",
                "finding_type": str(f["finding_type"]),
                "severity": str(f["severity"]),
                "file_path": chunk.filename,
                "line_number": int(f.get("line_number", chunk.start_line)),
                "message": str(f["message"]),
                "suggestion": str(f["suggestion"]) if f.get("suggestion") else None,
                "code_snippet": str(f["code_snippet"])[:500] if f.get("code_snippet") else None,
                "category": CATEGORY,
                "is_duplicate": False,
            }
        )

    return validated


async def run(
    chunks: list[CodeChunk],
    config: LLMConfig,
    call_llm: Callable[..., Awaitable[tuple[str, int, int]]],
) -> dict[str, Any]:
    """Analyse all code chunks for style violations.

    Args:
        chunks: Code chunks from the PR diff.
        config: Resolved LLM configuration to use.
        call_llm: Async callable matching the orchestrator's _call_llm signature.

    Returns:
        Dict with findings, tokens_input, tokens_output.
    """
    all_findings: list[dict] = []
    total_in = 0
    total_out = 0
    failures = 0
    last_error: str | None = None

    for chunk in chunks:
        prompt = _build_prompt(chunk)
        try:
            response_text, t_in, t_out = await call_llm(prompt, config)
            total_in += t_in
            total_out += t_out
            findings = _parse_findings(response_text, chunk)
            all_findings.extend(findings)
            logger.debug(
                "style_agent: %d findings in %s (lines %d-%d)",
                len(findings), chunk.filename, chunk.start_line, chunk.end_line,
            )
        except Exception as exc:
            failures += 1
            last_error = str(exc)
            logger.error(
                "style_agent: LLM call failed for %s: %s",
                chunk.filename, exc, exc_info=True,
            )

    logger.info(
        "style_agent: %d total findings across %d chunks",
        len(all_findings), len(chunks),
    )
    return {
        "findings": all_findings,
        "tokens_input": total_in,
        "tokens_output": total_out,
        "error_message": last_error if failures else None,
    }
