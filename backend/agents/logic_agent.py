"""Logic error analysis agent.

Analyses code chunks for logical bugs including off-by-one errors, null/None
dereferences, type mismatches, incorrect boundary conditions, and unreachable code.

Functions:
    run: Analyse a list of CodeChunk objects and return logic findings.
"""

import json
import logging
from typing import Any, Awaitable, Callable

from backend.agents.llm_router import LLMConfig
from backend.agents.orchestrator import MAX_CODE_CHARS
from backend.services.code_extractor import CodeChunk

logger = logging.getLogger(__name__)

CATEGORY = "logic"

_PROMPT_TEMPLATE = """\
You are an expert code reviewer specialising in logic errors and bugs. \
Analyse the following {language} code for logical mistakes.

File: {filename}
Lines {start_line}–{end_line}:

```{language}
{code}
```

Focus ONLY on real logic bugs, not style or performance issues:
- Off-by-one errors (wrong loop bounds, fencepost errors, index miscalculations)
- Null/None/undefined dereferences (accessing attributes without existence checks)
- Type mismatches (comparing incompatible types, wrong type passed to function)
- Incorrect boolean logic (wrong operator, negation errors, short-circuit mistakes)
- Missing edge case handling (empty list, zero, negative numbers, empty string)
- Unreachable code (dead branches, conditions that are always true/false)
- Incorrect error handling (swallowing exceptions, wrong exception type caught)
- Race conditions or incorrect state transitions in async code
- Wrong variable used (copy-paste errors, shadowed variables)
- Missing return value or incorrect return in all branches

Return ONLY valid JSON. Do not include any text outside the JSON object.

{{
    "findings": [
        {{
            "finding_type": "off_by_one",
            "severity": "high",
            "line_number": 42,
            "message": "Concise human-readable description of the bug",
            "suggestion": "Specific, actionable fix recommendation",
            "code_snippet": "offending line(s) of code (max 3 lines)"
        }}
    ]
}}

Severity levels: critical (data corruption or crash in normal usage), \
high (incorrect behaviour in common cases), \
medium (incorrect behaviour in edge cases), \
low (potential bug under unusual conditions).

Only report issues you are confident are real bugs. Do not speculate.
If you find no logic issues, return: {{"findings": []}}
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
        logger.warning("logic_agent: could not parse JSON for %s", chunk.filename)
        return []

    raw_findings = data.get("findings", [])
    if not isinstance(raw_findings, list):
        return []

    VALID_SEVERITIES = {"critical", "high", "medium", "low"}
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
                "agent_name": "logic",
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
    """Analyse all code chunks for logic errors.

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

    for chunk in chunks:
        prompt = _build_prompt(chunk)
        try:
            response_text, t_in, t_out = await call_llm(prompt, config)
            total_in += t_in
            total_out += t_out
            findings = _parse_findings(response_text, chunk)
            all_findings.extend(findings)
            logger.debug(
                "logic_agent: %d findings in %s (lines %d-%d)",
                len(findings), chunk.filename, chunk.start_line, chunk.end_line,
            )
        except Exception as exc:
            logger.error(
                "logic_agent: LLM call failed for %s: %s",
                chunk.filename, exc, exc_info=True,
            )

    logger.info(
        "logic_agent: %d total findings across %d chunks",
        len(all_findings), len(chunks),
    )
    return {"findings": all_findings, "tokens_input": total_in, "tokens_output": total_out}
