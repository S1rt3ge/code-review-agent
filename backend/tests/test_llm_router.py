"""Unit tests for LLMRouter.select() — all preference branches and auto fallback."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.agents.llm_router import LLMConfig, LLMRouter, MODEL_MAP


@pytest.fixture
def router() -> LLMRouter:
    return LLMRouter()


# ---------------------------------------------------------------------------
# Explicit preference: claude
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_claude_returns_config(router):
    cfg = await router.select(preference="claude", agent_name="security", api_key_claude="sk-test")
    assert cfg.provider == "claude"
    assert cfg.api_key == "sk-test"
    assert cfg.model == MODEL_MAP["claude"]["high"]
    assert "anthropic" in cfg.base_url


@pytest.mark.asyncio
async def test_select_claude_low_tier_for_style(router):
    cfg = await router.select(preference="claude", agent_name="style", api_key_claude="sk-test")
    assert cfg.model == MODEL_MAP["claude"]["low"]


@pytest.mark.asyncio
async def test_select_claude_raises_without_key(router):
    with pytest.raises(ValueError, match="Claude API key"):
        await router.select(preference="claude", agent_name="security", api_key_claude=None)


# ---------------------------------------------------------------------------
# Explicit preference: gpt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_gpt_returns_config(router):
    cfg = await router.select(preference="gpt", agent_name="logic", api_key_gpt="sk-gpt")
    assert cfg.provider == "gpt"
    assert cfg.api_key == "sk-gpt"
    assert cfg.model == MODEL_MAP["gpt"]["high"]


@pytest.mark.asyncio
async def test_select_gpt_raises_without_key(router):
    with pytest.raises(ValueError, match="OpenAI API key"):
        await router.select(preference="gpt", agent_name="logic", api_key_gpt=None)


# ---------------------------------------------------------------------------
# Explicit preference: local
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_local_returns_config_when_ollama_reachable(router):
    with patch.object(router, "_probe_ollama", new=AsyncMock(return_value=True)):
        cfg = await router.select(
            preference="local",
            agent_name="performance",
            ollama_enabled=True,
            ollama_host="http://localhost:11434",
        )
    assert cfg.provider == "local"
    assert cfg.api_key is None
    assert cfg.base_url == "http://localhost:11434"


@pytest.mark.asyncio
async def test_select_local_raises_when_not_enabled(router):
    with pytest.raises(ValueError, match="not available or not enabled"):
        await router.select(preference="local", ollama_enabled=False)


@pytest.mark.asyncio
async def test_select_local_raises_when_ollama_unreachable(router):
    with patch.object(router, "_probe_ollama", new=AsyncMock(return_value=False)):
        with pytest.raises(ValueError, match="not available or not enabled"):
            await router.select(preference="local", ollama_enabled=True)


# ---------------------------------------------------------------------------
# Auto mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_prefers_claude_over_gpt(router):
    cfg = await router.select(
        preference="auto",
        agent_name="security",
        api_key_claude="sk-claude",
        api_key_gpt="sk-gpt",
    )
    assert cfg.provider == "claude"


@pytest.mark.asyncio
async def test_auto_falls_back_to_gpt_when_no_claude(router):
    cfg = await router.select(
        preference="auto",
        agent_name="security",
        api_key_claude=None,
        api_key_gpt="sk-gpt",
    )
    assert cfg.provider == "gpt"


@pytest.mark.asyncio
async def test_auto_falls_back_to_local_when_only_ollama(router):
    with patch.object(router, "_probe_ollama", new=AsyncMock(return_value=True)):
        cfg = await router.select(
            preference="auto",
            agent_name="security",
            api_key_claude=None,
            api_key_gpt=None,
            ollama_enabled=True,
            ollama_host="http://localhost:11434",
        )
    assert cfg.provider == "local"


@pytest.mark.asyncio
async def test_auto_raises_when_nothing_configured(router):
    with pytest.raises(ValueError, match="No LLM provider"):
        await router.select(
            preference="auto",
            api_key_claude=None,
            api_key_gpt=None,
            ollama_enabled=False,
        )


# ---------------------------------------------------------------------------
# Unknown preference
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_preference_raises(router):
    with pytest.raises(ValueError, match="Unknown LLM preference"):
        await router.select(preference="unknown_llm")


# ---------------------------------------------------------------------------
# Probe helper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_probe_ollama_returns_true_on_200(router):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await router._probe_ollama("http://localhost:11434")
    assert result is True


@pytest.mark.asyncio
async def test_probe_ollama_returns_false_on_connection_error(router):
    import httpx
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await router._probe_ollama("http://localhost:11434")
    assert result is False
