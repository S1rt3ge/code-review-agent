"""Performance analysis agent.

Analyses code chunks for performance issues including N+1 queries,
inefficient algorithms, memory leaks, unnecessary copies, and blocking I/O.

Functions:
    run: Analyse a list of CodeChunk objects and return performance findings.
"""

import json
import logging
from typing import Any, Awaitable, Callable

from backend.agents.llm_router import LLMConfig
from backend.agents.orchestrator import MAX_CODE_CHARS
from backend.services.code_extractor import CodeChunk

logger = logging.getLogger(__name__)

CATEGORY = "performance"

_PROMPT_TEMPLATE = """\
You are an expert performance code reviewer. Analyse the following {language} code \
for performance issues.

File: {filename}
Lines {start_line}–{end_line}:

```{language}
{code}
```

Focus ONLY on real performance problems, not style or security issues:
- N+1 database queries (queries inside loops without prefetching/batching)
- O(n²) or worse algorithms where a linear solution exists
- Memory leaks (objects growing unbounded, unclosed resources, circular refs)
- Large unnecessary copies (copying big lists/dicts instead of using views/refs)
- Blocking I/O in async context (time.sleep, requests.get, open() without async)
- Repeated expensive computations that could be cached or hoisted out of loops
- Inefficient data structures (list for membership checks instead of set)
- Missing database indexes implied by filter/order patterns

Return ONLY valid JSON. Do not include any text outside the JSON object.

{{
    "findings": [
        {{
            "finding_type": "n_plus_one_query",
            "severity": "high",
            "line_number": 42,
            "message": "Concise human-readable description of the issue",
            "suggestion": "Specific, actionable fix recommendation",
            "code_snippet": "offending line(s) of code (max 3 lines)"
        }}
    ]
}}

Severity levels: critical (causes OOM or severe production degradation), \
high (significant slowdown under normal load), \
medium (noticeable under moderate load), low (minor inefficiency).

If you find no performance issues, return: {{"findings": []}}
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
        logger.warning(
            "performance_agent: could not parse JSON for %s", chunk.filename
        )
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
                "agent_name": "performance",
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
    """Analyse all code chunks for performance issues.

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
                "performance_agent: %d findings in %s (lines %d-%d)",
                len(findings), chunk.filename, chunk.start_line, chunk.end_line,
            )
        except Exception as exc:
            logger.error(
                "performance_agent: LLM call failed for %s: %s",
                chunk.filename, exc, exc_info=True,
            )

    logger.info(
        "performance_agent: %d total findings across %d chunks",
        len(all_findings), len(chunks),
    )
    return {"findings": all_findings, "tokens_input": total_in, "tokens_output": total_out}
