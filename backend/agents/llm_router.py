"""LLM selection router.

Selects the appropriate LLM provider (Claude, GPT, or local Ollama)
based on user settings, availability, and agent requirements.

Classes:
    LLMProvider: Enum of supported LLM providers.
    LLMConfig: Configuration for a selected LLM.
    LLMRouter: Selects and returns the best available LLM for a given request.
"""

import logging
from dataclasses import dataclass
from enum import Enum

import httpx

from backend.config import settings as app_settings

logger = logging.getLogger(__name__)

# Timeout for health-check probes when selecting an LLM (seconds).
PROBE_TIMEOUT = 5

# Quality scores used when auto-selecting a provider.
# Higher is better.
QUALITY_SCORES: dict[str, int] = {
    "claude": 5,
    "gpt": 4,
    "local": 2,
}

# Agent-to-model tier mapping.  Agents that need deep reasoning use
# the "high" tier; simpler tasks use "low".
AGENT_TIER: dict[str, str] = {
    "security": "high",
    "performance": "high",
    "logic": "high",
    "style": "low",
}

# Model names per provider and tier.
MODEL_MAP: dict[str, dict[str, str]] = {
    "claude": {
        "high": "claude-opus-4-6",
        "low": "claude-sonnet-4-6",
    },
    "gpt": {
        "high": "gpt-4o",
        "low": "gpt-4o-mini",
    },
    "local": {
        "high": "qwen2.5-coder:32b",
        "low": "qwen2.5-coder:32b",
    },
}


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    CLAUDE = "claude"
    GPT = "gpt"
    LOCAL = "local"


@dataclass(frozen=True)
class LLMConfig:
    """Resolved configuration for a selected LLM.

    Attributes:
        provider: The LLM provider name.
        model: Specific model identifier to use for the request.
        api_key: API key (None for local models).
        base_url: Base URL for the provider API.
    """

    provider: str
    model: str
    api_key: str | None
    base_url: str


class LLMRouter:
    """Select the best available LLM provider.

    The router respects user preferences when the requested provider is
    available, and falls back through the priority chain when it is not.
    """

    async def select(
        self,
        preference: str = "auto",
        agent_name: str = "security",
        api_key_claude: str | None = None,
        api_key_gpt: str | None = None,
        ollama_enabled: bool = False,
        ollama_host: str | None = None,
    ) -> LLMConfig:
        """Select the LLM provider and model for the given request.

        Args:
            preference: User preference (``auto``, ``claude``, ``gpt``, ``local``).
            agent_name: Name of the agent requesting the LLM (affects model tier).
            api_key_claude: User's Claude API key (decrypted), or None.
            api_key_gpt: User's GPT API key (decrypted), or None.
            ollama_enabled: Whether the user has Ollama enabled.
            ollama_host: Ollama base URL.

        Returns:
            LLMConfig with provider, model, key, and base URL.

        Raises:
            ValueError: If no LLM is available for the requested preference.
        """
        tier = AGENT_TIER.get(agent_name, "high")

        # Resolve effective keys (user key overrides app-level key)
        claude_key = api_key_claude or app_settings.anthropic_api_key
        gpt_key = api_key_gpt or app_settings.openai_api_key
        effective_ollama_host = ollama_host or app_settings.ollama_host

        # Explicit user preference
        if preference == "local":
            if ollama_enabled:
                reachable = await self._probe_ollama(effective_ollama_host)
                if reachable:
                    return LLMConfig(
                        provider="local",
                        model=MODEL_MAP["local"][tier],
                        api_key=None,
                        base_url=effective_ollama_host,
                    )
            raise ValueError("Local (Ollama) is not available or not enabled")

        if preference == "claude":
            if claude_key:
                return LLMConfig(
                    provider="claude",
                    model=MODEL_MAP["claude"][tier],
                    api_key=claude_key,
                    base_url="https://api.anthropic.com",
                )
            raise ValueError("Claude API key is not configured")

        if preference == "gpt":
            if gpt_key:
                return LLMConfig(
                    provider="gpt",
                    model=MODEL_MAP["gpt"][tier],
                    api_key=gpt_key,
                    base_url="https://api.openai.com/v1",
                )
            raise ValueError("OpenAI API key is not configured")

        # Auto mode: pick the best available
        if preference == "auto":
            return await self._auto_select(
                tier=tier,
                claude_key=claude_key,
                gpt_key=gpt_key,
                ollama_enabled=ollama_enabled,
                ollama_host=effective_ollama_host,
            )

        raise ValueError(f"Unknown LLM preference: {preference}")

    async def _auto_select(
        self,
        tier: str,
        claude_key: str | None,
        gpt_key: str | None,
        ollama_enabled: bool,
        ollama_host: str,
    ) -> LLMConfig:
        """Pick the highest-quality available provider.

        Args:
            tier: Model tier (``high`` or ``low``).
            claude_key: Resolved Claude API key or None.
            gpt_key: Resolved GPT API key or None.
            ollama_enabled: Whether Ollama is enabled.
            ollama_host: Ollama base URL.

        Returns:
            LLMConfig for the best available provider.

        Raises:
            ValueError: If no provider is available at all.
        """
        candidates: list[tuple[str, int]] = []

        if claude_key:
            candidates.append(("claude", QUALITY_SCORES["claude"]))
        if gpt_key:
            candidates.append(("gpt", QUALITY_SCORES["gpt"]))
        if ollama_enabled:
            reachable = await self._probe_ollama(ollama_host)
            if reachable:
                candidates.append(("local", QUALITY_SCORES["local"]))

        if not candidates:
            raise ValueError(
                "No LLM provider is configured. "
                "Set an API key or enable Ollama in settings."
            )

        best_provider = max(candidates, key=lambda c: c[1])[0]

        key_map: dict[str, str | None] = {
            "claude": claude_key,
            "gpt": gpt_key,
            "local": None,
        }
        url_map: dict[str, str] = {
            "claude": "https://api.anthropic.com",
            "gpt": "https://api.openai.com/v1",
            "local": ollama_host,
        }

        return LLMConfig(
            provider=best_provider,
            model=MODEL_MAP[best_provider][tier],
            api_key=key_map[best_provider],
            base_url=url_map[best_provider],
        )

    async def _probe_ollama(self, host: str) -> bool:
        """Check if Ollama is reachable.

        Args:
            host: Ollama base URL.

        Returns:
            True if the Ollama server responds, False otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as client:
                resp = await client.get(f"{host}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False


# Module-level singleton.
llm_router = LLMRouter()
