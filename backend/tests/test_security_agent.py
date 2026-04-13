"""Tests for backend/agents/security_agent.py.

Covers:
    _parse_findings: JSON parsing, field validation, severity filtering
    run: full agent execution with mocked call_llm
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents import security_agent
from backend.agents.security_agent import _parse_findings, run
from backend.agents.llm_router import LLMConfig
from backend.services.code_extractor import CodeChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(filename="app.py", language="python", start=1, end=10, content="x = 1"):
    return CodeChunk(
        filename=filename,
        language=language,
        start_line=start,
        end_line=end,
        content=content,
        added_lines={1},
    )


def _make_config():
    return LLMConfig(
        provider="claude",
        model="claude-opus-4-6",
        api_key="test-key",
        base_url="https://api.anthropic.com",
    )


# ---------------------------------------------------------------------------
# _parse_findings
# ---------------------------------------------------------------------------


def test_parse_findings_valid_json():
    raw = json.dumps({
        "findings": [
            {
                "finding_type": "sql_injection",
                "severity": "critical",
                "line_number": 5,
                "message": "SQL injection via f-string",
                "suggestion": "Use parameterised queries",
                "code_snippet": "cursor.execute(f'SELECT * FROM users WHERE id={id}')",
            }
        ]
    })
    chunk = _make_chunk()
    result = _parse_findings(raw, chunk)
    assert len(result) == 1
    assert result[0]["finding_type"] == "sql_injection"
    assert result[0]["severity"] == "critical"
    assert result[0]["file_path"] == "app.py"
    assert result[0]["line_number"] == 5


def test_parse_findings_strips_markdown_fences():
    raw = "```json\n" + json.dumps({"findings": []}) + "\n```"
    chunk = _make_chunk()
    result = _parse_findings(raw, chunk)
    assert result == []


def test_parse_findings_invalid_json_returns_empty():
    chunk = _make_chunk()
    result = _parse_findings("not valid json at all", chunk)
    assert result == []


def test_parse_findings_invalid_severity_skipped():
    raw = json.dumps({
        "findings": [
            {
                "finding_type": "xss",
                "severity": "oops",  # invalid
                "line_number": 1,
                "message": "XSS",
            }
        ]
    })
    chunk = _make_chunk()
    result = _parse_findings(raw, chunk)
    assert result == []


def test_parse_findings_missing_required_field_skipped():
    raw = json.dumps({
        "findings": [
            {
                "finding_type": "injection",
                # missing: severity, line_number, message
            }
        ]
    })
    chunk = _make_chunk()
    result = _parse_findings(raw, chunk)
    assert result == []


def test_parse_findings_no_suggestion_allowed():
    raw = json.dumps({
        "findings": [
            {
                "finding_type": "hardcoded_secret",
                "severity": "high",
                "line_number": 3,
                "message": "Hardcoded API key",
            }
        ]
    })
    chunk = _make_chunk()
    result = _parse_findings(raw, chunk)
    assert len(result) == 1
    assert result[0]["suggestion"] is None


def test_parse_findings_code_snippet_truncated_at_500():
    raw = json.dumps({
        "findings": [
            {
                "finding_type": "injection",
                "severity": "medium",
                "line_number": 1,
                "message": "msg",
                "code_snippet": "x" * 600,
            }
        ]
    })
    chunk = _make_chunk()
    result = _parse_findings(raw, chunk)
    assert len(result[0]["code_snippet"]) == 500


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_returns_findings():
    chunk = _make_chunk(content="password = 'hunter2'")
    config = _make_config()

    response_payload = json.dumps({
        "findings": [
            {
                "finding_type": "hardcoded_secret",
                "severity": "high",
                "line_number": 1,
                "message": "Hardcoded password",
                "suggestion": "Use environment variable",
            }
        ]
    })

    mock_call_llm = AsyncMock(return_value=(response_payload, 100, 50))

    result = await run(chunks=[chunk], config=config, call_llm=mock_call_llm)

    assert len(result["findings"]) == 1
    assert result["findings"][0]["finding_type"] == "hardcoded_secret"
    assert result["tokens_input"] == 100
    assert result["tokens_output"] == 50


@pytest.mark.asyncio
async def test_run_empty_chunks_returns_empty():
    config = _make_config()
    mock_call_llm = AsyncMock(return_value=('{"findings": []}', 0, 0))

    result = await run(chunks=[], config=config, call_llm=mock_call_llm)

    assert result["findings"] == []
    mock_call_llm.assert_not_called()


@pytest.mark.asyncio
async def test_run_llm_error_returns_empty():
    chunk = _make_chunk()
    config = _make_config()

    mock_call_llm = AsyncMock(side_effect=Exception("API error"))

    result = await run(chunks=[chunk], config=config, call_llm=mock_call_llm)

    assert result["findings"] == []
    assert result["tokens_input"] == 0


@pytest.mark.asyncio
async def test_run_multiple_chunks_aggregates():
    chunk1 = _make_chunk(filename="a.py", content="x=1")
    chunk2 = _make_chunk(filename="b.py", content="y=2")
    config = _make_config()

    def make_resp(filename):
        return json.dumps({
            "findings": [{
                "finding_type": "test",
                "severity": "low",
                "line_number": 1,
                "message": f"issue in {filename}",
            }]
        })

    mock_call_llm = AsyncMock(side_effect=[
        (make_resp("a.py"), 50, 20),
        (make_resp("b.py"), 50, 20),
    ])

    result = await run(chunks=[chunk1, chunk2], config=config, call_llm=mock_call_llm)

    assert len(result["findings"]) == 2
    assert result["tokens_input"] == 100
    assert result["tokens_output"] == 40
