"""Tests for performance_agent, style_agent, and logic_agent.

Each agent follows the same contract as security_agent, so we test:
- _parse_findings: valid JSON, invalid severity, missing fields, markdown fences
- run: happy path, empty chunks, LLM error
"""

import json
from unittest.mock import AsyncMock

import pytest

from backend.agents import logic_agent, performance_agent, style_agent
from backend.agents.llm_router import LLMConfig
from backend.services.code_extractor import CodeChunk


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _chunk(filename="app.py", language="python"):
    return CodeChunk(
        filename=filename,
        language=language,
        start_line=1,
        end_line=20,
        content="for i in range(len(items)):\n    db.query(f'SELECT * FROM t WHERE id={i}')",
        added_lines={1, 2},
    )


def _config():
    return LLMConfig(
        provider="claude",
        model="claude-opus-4-6",
        api_key="test",
        base_url="https://api.anthropic.com",
    )


def _resp(findings: list[dict]) -> str:
    return json.dumps({"findings": findings})


def _finding(agent: str, ftype: str, severity: str, line: int = 1) -> dict:
    return {
        "finding_type": ftype,
        "severity": severity,
        "line_number": line,
        "message": f"{ftype} detected",
        "suggestion": "fix it",
    }


# ---------------------------------------------------------------------------
# performance_agent
# ---------------------------------------------------------------------------


def test_perf_parse_valid():
    raw = _resp([_finding("performance", "n_plus_one_query", "high")])
    result = performance_agent._parse_findings(raw, _chunk())
    assert len(result) == 1
    assert result[0]["agent_name"] == "performance"
    assert result[0]["category"] == "performance"


def test_perf_parse_invalid_severity_skipped():
    raw = _resp([_finding("performance", "slow_loop", "blocker")])  # not a valid severity
    result = performance_agent._parse_findings(raw, _chunk())
    assert result == []


def test_perf_parse_strips_fences():
    raw = "```json\n" + _resp([]) + "\n```"
    result = performance_agent._parse_findings(raw, _chunk())
    assert result == []


@pytest.mark.asyncio
async def test_perf_run_returns_findings():
    mock_llm = AsyncMock(return_value=(_resp([_finding("performance", "n_plus_one", "high")]), 80, 30))
    result = await performance_agent.run([_chunk()], _config(), mock_llm)
    assert len(result["findings"]) == 1
    assert result["tokens_input"] == 80


@pytest.mark.asyncio
async def test_perf_run_empty_chunks():
    mock_llm = AsyncMock()
    result = await performance_agent.run([], _config(), mock_llm)
    assert result["findings"] == []
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_perf_run_llm_error_returns_empty():
    mock_llm = AsyncMock(side_effect=Exception("timeout"))
    result = await performance_agent.run([_chunk()], _config(), mock_llm)
    assert result["findings"] == []


# ---------------------------------------------------------------------------
# style_agent
# ---------------------------------------------------------------------------


def test_style_parse_valid():
    raw = _resp([_finding("style", "missing_docstring", "low")])
    result = style_agent._parse_findings(raw, _chunk())
    assert len(result) == 1
    assert result[0]["agent_name"] == "style"
    assert result[0]["severity"] == "low"


def test_style_parse_high_severity_rejected():
    # style agent only accepts medium/low/info
    raw = _resp([_finding("style", "naming", "high")])
    result = style_agent._parse_findings(raw, _chunk())
    assert result == []


def test_style_parse_info_accepted():
    raw = _resp([_finding("style", "line_too_long", "info")])
    result = style_agent._parse_findings(raw, _chunk())
    assert len(result) == 1


@pytest.mark.asyncio
async def test_style_run_aggregates_multiple_chunks():
    chunk1 = _chunk("a.py")
    chunk2 = _chunk("b.py")
    mock_llm = AsyncMock(side_effect=[
        (_resp([_finding("style", "naming", "low")]), 40, 10),
        (_resp([_finding("style", "missing_docstring", "medium")]), 40, 10),
    ])
    result = await style_agent.run([chunk1, chunk2], _config(), mock_llm)
    assert len(result["findings"]) == 2
    assert result["tokens_input"] == 80


@pytest.mark.asyncio
async def test_style_run_llm_error_returns_empty():
    mock_llm = AsyncMock(side_effect=Exception("api down"))
    result = await style_agent.run([_chunk()], _config(), mock_llm)
    assert result["findings"] == []


# ---------------------------------------------------------------------------
# logic_agent
# ---------------------------------------------------------------------------


def test_logic_parse_valid():
    raw = _resp([_finding("logic", "off_by_one", "high")])
    result = logic_agent._parse_findings(raw, _chunk())
    assert len(result) == 1
    assert result[0]["agent_name"] == "logic"
    assert result[0]["finding_type"] == "off_by_one"


def test_logic_parse_missing_required_field():
    raw = json.dumps({"findings": [{"finding_type": "null_deref"}]})
    result = logic_agent._parse_findings(raw, _chunk())
    assert result == []


def test_logic_parse_invalid_json():
    result = logic_agent._parse_findings("definitely not json", _chunk())
    assert result == []


@pytest.mark.asyncio
async def test_logic_run_returns_findings():
    mock_llm = AsyncMock(return_value=(
        _resp([_finding("logic", "null_deref", "critical")]), 100, 50
    ))
    result = await logic_agent.run([_chunk()], _config(), mock_llm)
    assert len(result["findings"]) == 1
    assert result["findings"][0]["severity"] == "critical"
    assert result["tokens_output"] == 50


@pytest.mark.asyncio
async def test_logic_run_empty_chunks():
    mock_llm = AsyncMock()
    result = await logic_agent.run([], _config(), mock_llm)
    assert result["findings"] == []
    mock_llm.assert_not_called()
