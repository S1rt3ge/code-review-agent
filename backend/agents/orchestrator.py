"""LangGraph orchestrator for multi-agent code review.

Runs analysis agents in parallel, collects findings, and returns aggregated
results with per-agent execution metadata.

Functions:
    run_graph: Main entry point — dispatches agents for a set of code chunks.

Private helpers:
    _call_llm: Provider-agnostic LLM invocation (Claude / OpenAI / Ollama).
    _run_agent: Wrap one agent function with timeout and error handling.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from backend.agents.llm_router import LLMConfig, llm_router
from backend.services.code_extractor import CodeChunk

logger = logging.getLogger(__name__)

# Per-agent timeout in seconds (matches CLAUDE.md specification).
AGENT_TIMEOUT = 30

# Maximum characters of code fed to each agent per call.
# Keeps prompts within context limits for all supported models.
MAX_CODE_CHARS = 12_000


# ---------------------------------------------------------------------------
# LLM caller (provider-agnostic)
# ---------------------------------------------------------------------------


async def _call_llm(prompt: str, config: LLMConfig) -> tuple[str, int, int]:
    """Invoke the LLM and return (response_text, tokens_in, tokens_out).

    Supports Claude (via ``anthropic``), OpenAI GPT, and Ollama (OpenAI-
    compatible API).

    Args:
        prompt: The full prompt string to send to the model.
        config: Resolved LLM configuration from the router.

    Returns:
        Tuple of (response text, prompt tokens, completion tokens).

    Raises:
        Exception: Propagated from the underlying SDK on API errors.
    """
    if config.provider == "claude":
        import anthropic  # noqa: PLC0415

        client = anthropic.AsyncAnthropic(api_key=config.api_key)
        message = await client.messages.create(
            model=config.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text
        return text, message.usage.input_tokens, message.usage.output_tokens

    # OpenAI (gpt) or Ollama (local) — both speak the OpenAI API protocol.
    from openai import AsyncOpenAI  # noqa: PLC0415

    base_url = config.base_url if config.provider == "local" else None
    api_key = config.api_key or "ollama"  # Ollama ignores the key
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    completion = await client.chat.completions.create(
        model=config.model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=2048,
    )
    text = completion.choices[0].message.content or ""
    usage = completion.usage
    return text, (usage.prompt_tokens if usage else 0), (usage.completion_tokens if usage else 0)


# ---------------------------------------------------------------------------
# Agent runner with timeout + error isolation
# ---------------------------------------------------------------------------


async def _run_agent(
    agent_name: str,
    chunks: list[CodeChunk],
    llm_preference: str,
    api_key_claude: str | None,
    api_key_gpt: str | None,
    ollama_enabled: bool,
    ollama_host: str | None,
    on_progress: Callable[[str, str], Awaitable[None]] | None = None,
) -> tuple[list[dict], dict]:
    """Run a single named agent and return (findings, execution_meta).

    Selects the LLM config per agent so each agent gets the correct model
    tier (e.g. style → Sonnet, security/logic/performance → Opus).

    Args:
        agent_name: One of ``security``, ``performance``, ``style``, ``logic``.
        chunks: Code chunks to analyse.
        llm_preference: LLM provider preference (``auto`` / ``claude`` / ``gpt`` / ``local``).
        api_key_claude: Decrypted Claude API key or None.
        api_key_gpt: Decrypted GPT API key or None.
        ollama_enabled: Whether Ollama is enabled.
        ollama_host: Ollama base URL override.
        on_progress: Optional async callback ``(agent_name, status) → None``.

    Returns:
        Tuple of (flat findings list, execution metadata dict).
    """
    started_at = datetime.now(timezone.utc)
    findings: list[dict] = []
    error_message: str | None = None
    tokens_in = 0
    tokens_out = 0

    if on_progress:
        try:
            await on_progress(agent_name, "running")
        except Exception:
            pass  # Never let progress callbacks crash the agent

    # Select LLM per agent so the correct model tier is used
    # (e.g. style → Sonnet/low, security/logic/performance → Opus/high).
    try:
        config = await llm_router.select(
            preference=llm_preference,
            agent_name=agent_name,
            api_key_claude=api_key_claude,
            api_key_gpt=api_key_gpt,
            ollama_enabled=ollama_enabled,
            ollama_host=ollama_host,
        )
    except ValueError as exc:
        error_message = str(exc)
        logger.warning("No LLM for agent '%s': %s", agent_name, exc)
        completed_at = datetime.now(timezone.utc)
        if on_progress:
            try:
                await on_progress(agent_name, "error")
            except Exception:
                pass
        return [], {
            "status": "error",
            "started_at": started_at,
            "completed_at": completed_at,
            "tokens_input": 0,
            "tokens_output": 0,
            "findings_count": 0,
            "error_message": error_message,
        }

    try:
        # Dynamic import so adding new agents never requires touching this file.
        module = __import__(
            f"backend.agents.{agent_name}_agent",
            fromlist=["run"],
        )
        agent_fn = module.run

        result = await asyncio.wait_for(
            agent_fn(chunks=chunks, config=config, call_llm=_call_llm),
            timeout=AGENT_TIMEOUT,
        )
        findings = result.get("findings", [])
        tokens_in = result.get("tokens_input", 0)
        tokens_out = result.get("tokens_output", 0)

        # Tag each finding with the agent name.
        for f in findings:
            f.setdefault("agent_name", agent_name)

    except asyncio.TimeoutError:
        error_message = f"Agent '{agent_name}' timed out after {AGENT_TIMEOUT}s"
        logger.warning(error_message)

    except ModuleNotFoundError:
        error_message = f"Agent module 'backend.agents.{agent_name}_agent' not found (not yet implemented)"
        logger.debug(error_message)

    except Exception as exc:
        error_message = str(exc)
        logger.error("Agent '%s' failed: %s", agent_name, exc, exc_info=True)

    completed_at = datetime.now(timezone.utc)
    agent_status = "error" if error_message else "done"

    if on_progress:
        try:
            await on_progress(agent_name, agent_status)
        except Exception:
            pass

    meta = {
        "status": agent_status,
        "started_at": started_at,
        "completed_at": completed_at,
        "tokens_input": tokens_in,
        "tokens_output": tokens_out,
        "findings_count": len(findings),
        "error_message": error_message,
    }
    return findings, meta


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_graph(
    review_id: uuid.UUID,
    chunks: list[CodeChunk],
    agents: list[str],
    llm_preference: str = "auto",
    api_key_claude: str | None = None,
    api_key_gpt: str | None = None,
    ollama_enabled: bool = False,
    ollama_host: str | None = None,
    on_progress: Callable[[str, str], Awaitable[None]] | None = None,
) -> tuple[list[dict], dict[str, dict]]:
    """Run all selected agents in parallel and aggregate their findings.

    Args:
        review_id: Review UUID (used only for logging).
        chunks: Code chunks extracted from the PR diff.
        agents: Agent names to run, e.g. ``["security", "style"]``.
        llm_preference: LLM selection preference (``auto`` / ``claude`` / ``gpt`` / ``local``).
        api_key_claude: User's decrypted Claude API key (or None to use app key).
        api_key_gpt: User's decrypted GPT API key (or None to use app key).
        ollama_enabled: Whether Ollama is enabled for this user.
        ollama_host: Ollama base URL override.
        on_progress: Optional async callback ``(agent_name, status) → None`` called
            when each agent starts (``"running"``) and finishes (``"done"``/``"error"``).

    Returns:
        Tuple of (flat findings list, per-agent execution metadata dict).
    """
    if not chunks or not agents:
        logger.info("run_graph: no chunks or agents; skipping (review %s)", review_id)
        empty_meta = {
            a: {
                "status": "done",
                "started_at": datetime.now(timezone.utc),
                "completed_at": datetime.now(timezone.utc),
                "tokens_input": 0,
                "tokens_output": 0,
                "findings_count": 0,
                "error_message": None,
            }
            for a in agents
        }
        return [], empty_meta

    logger.info("run_graph: starting %d agents for review %s", len(agents), review_id)

    # Run all agents concurrently. Each agent selects its own LLM config so
    # the correct model tier is used (style → Sonnet, others → Opus).
    tasks = [
        _run_agent(
            agent_name,
            chunks,
            llm_preference,
            api_key_claude,
            api_key_gpt,
            ollama_enabled,
            ollama_host,
            on_progress,
        )
        for agent_name in agents
    ]
    results = await asyncio.gather(*tasks)

    all_findings: list[dict] = []
    agent_results: dict[str, dict] = {}

    for agent_name, (findings, meta) in zip(agents, results):
        all_findings.extend(findings)
        agent_results[agent_name] = meta

    logger.info(
        "run_graph complete: %d findings from %d agents (review %s)",
        len(all_findings),
        len(agents),
        review_id,
    )
    return all_findings, agent_results
