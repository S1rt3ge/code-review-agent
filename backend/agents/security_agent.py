"""Security analysis agent.

Analyses code chunks for security vulnerabilities including injection attacks,
authentication flaws, hardcoded secrets, weak cryptography, and insecure
data handling.

Functions:
    run: Analyse a list of CodeChunk objects and return security findings.
"""

import json
import logging
from typing import Any, Awaitable, Callable

from backend.agents.llm_router import LLMConfig
from backend.agents.orchestrator import MAX_CODE_CHARS
from backend.services.code_extractor import CodeChunk

logger = logging.getLogger(__name__)

# Severity values used by this agent.
SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

# Issue categories this agent reports under.
CATEGORY = "security"

_PROMPT_TEMPLATE = """\
You are an expert security code reviewer. Analyse the following {language} code \
for security vulnerabilities.

File: {filename}
Lines {start_line}–{end_line}:

```{language}
{code}
```

Focus ONLY on real security issues, not style or logic errors:
- SQL / NoSQL / command injection (string interpolation in queries/exec calls)
- XSS vulnerabilities (unsanitised user input rendered as HTML)
- Authentication and authorisation flaws (missing checks, privilege escalation)
- Hardcoded secrets, API keys, passwords, or tokens
- Weak or broken cryptography (MD5, SHA-1, ECB mode, predictable randoms)
- Insecure direct object references (IDOR)
- Path traversal vulnerabilities
- Sensitive data exposure (logging passwords, PII in plain text)
- Insecure deserialization

Return ONLY valid JSON. Do not include any text outside the JSON object.

{{
    "findings": [
        {{
            "finding_type": "sql_injection",
            "severity": "critical",
            "line_number": 42,
            "message": "Concise human-readable description of the issue",
            "suggestion": "Specific, actionable fix recommendation",
            "code_snippet": "offending line(s) of code (max 3 lines)"
        }}
    ]
}}

Severity levels: critical (exploitable remotely, data breach risk), \
high (exploitable with some effort), medium (requires specific conditions), \
low (minor risk / defence-in-depth issue).

If you find no security issues, return: {{"findings": []}}
"""


def _build_prompt(chunk: CodeChunk) -> str:
    """Format the security analysis prompt for a single code chunk.

    Args:
        chunk: Code chunk to analyse.

    Returns:
        Formatted prompt string.
    """
    code = chunk.content[:MAX_CODE_CHARS]
    return _PROMPT_TEMPLATE.format(
        language=chunk.language,
        filename=chunk.filename,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        code=code,
    )


def _parse_findings(raw: str, chunk: CodeChunk) -> list[dict]:
    """Parse LLM JSON output into a validated list of finding dicts.

    Malformed JSON and findings that are missing required fields are silently
    dropped to keep the pipeline running even when the LLM misbehaves.

    Args:
        raw: Raw response string from the LLM.
        chunk: The code chunk being analysed (used for fallback metadata).

    Returns:
        List of validated finding dicts.
    """
    # Strip markdown code fences if the model wrapped the response.
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
            "security_agent: could not parse JSON from LLM response for %s",
            chunk.filename,
        )
        return []

    raw_findings = data.get("findings", [])
    if not isinstance(raw_findings, list):
        return []

    VALID_SEVERITIES = {SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW}
    validated: list[dict] = []

    for f in raw_findings:
        if not isinstance(f, dict):
            continue
        # Required fields
        if not all(k in f for k in ("finding_type", "severity", "line_number", "message")):
            continue
        if f["severity"] not in VALID_SEVERITIES:
            continue

        validated.append(
            {
                "agent_name": "security",
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
    """Analyse all code chunks for security vulnerabilities.

    Each chunk is analysed independently. Results from all chunks are
    combined into a single flat findings list.

    Args:
        chunks: Code chunks from the PR diff.
        config: Resolved LLM configuration to use.
        call_llm: Async callable matching the orchestrator's ``_call_llm`` signature.

    Returns:
        Dict with ``findings`` (list), ``tokens_input`` (int), ``tokens_output`` (int).
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
                "security_agent: %d findings in %s (lines %d-%d)",
                len(findings),
                chunk.filename,
                chunk.start_line,
                chunk.end_line,
            )
        except Exception as exc:
            failures += 1
            last_error = str(exc)
            logger.error(
                "security_agent: LLM call failed for %s: %s",
                chunk.filename,
                exc,
                exc_info=True,
            )

    logger.info(
        "security_agent: %d total findings across %d chunks",
        len(all_findings),
        len(chunks),
    )
    return {
        "findings": all_findings,
        "tokens_input": total_in,
        "tokens_output": total_out,
        "error_message": last_error if failures else None,
    }
