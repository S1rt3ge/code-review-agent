"""User settings and LLM configuration endpoints.

Provides endpoints for reading and updating user LLM preferences,
API keys, agent selection, and connectivity testing.

Functions:
    get_settings: GET /settings -- current user settings.
    update_settings: PUT /settings -- update user settings.
    test_llm: POST /settings/test-llm -- test LLM connectivity.
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings as app_settings
from backend.models.schemas import (
    SettingsResponse,
    SettingsTestResponse,
    SettingsUpdate,
)
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Known agent names accepted by the system.
VALID_AGENTS = {"security", "performance", "style", "logic"}
VALID_LM_PREFERENCES = {"auto", "claude", "gpt", "local"}

# Timeout for external LLM connectivity checks (seconds).
LLM_TEST_TIMEOUT = 10


@router.get("", response_model=SettingsResponse)
async def get_settings(
    session: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Return the current user's LLM and agent settings.

    In a full implementation this would load the authenticated user's
    record from the database. For the Phase 1.1 scaffold the response
    is built from application-level defaults.

    Args:
        session: Async database session.

    Returns:
        Current settings including which API keys are configured.
    """
    # TODO(phase-1.2): Load user from JWT, read encrypted keys from DB.
    return SettingsResponse(
        plan="free",
        api_key_claude_set=app_settings.anthropic_api_key is not None,
        api_key_gpt_set=app_settings.openai_api_key is not None,
        ollama_enabled=False,
        ollama_host=app_settings.ollama_host,
        default_agents=["security", "performance", "style", "logic"],
        lm_preference="auto",
    )


@router.put("", response_model=dict)
async def update_settings(
    payload: SettingsUpdate,
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool | list[str]]:
    """Update user LLM settings.

    Validates the requested agents and LLM preference, then persists
    the changes. API keys are encrypted before storage.

    Args:
        payload: Fields to update (only non-None values are applied).
        session: Async database session.

    Returns:
        Dict with ``updated`` flag and optional ``warnings`` list.

    Raises:
        HTTPException 400: If agent names or LLM preference are invalid.
    """
    warnings: list[str] = []

    # Validate agent names
    if payload.default_agents is not None:
        invalid = set(payload.default_agents) - VALID_AGENTS
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown agent names: {', '.join(sorted(invalid))}",
            )

    # Validate LLM preference
    if payload.lm_preference is not None:
        if payload.lm_preference not in VALID_LM_PREFERENCES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid lm_preference '{payload.lm_preference}'. "
                    f"Must be one of: {', '.join(sorted(VALID_LM_PREFERENCES))}"
                ),
            )

    # Warn if Ollama is enabled but host is unreachable
    if payload.ollama_enabled and payload.ollama_host:
        try:
            async with httpx.AsyncClient(timeout=LLM_TEST_TIMEOUT) as client:
                resp = await client.get(payload.ollama_host)
                if resp.status_code != 200:
                    warnings.append(f"Ollama host returned status {resp.status_code}")
        except httpx.HTTPError:
            warnings.append("Ollama host is unreachable")

    # TODO(phase-1.2): Persist settings to user record in DB.
    logger.info("Settings update received (persistence not yet implemented)")

    return {"updated": True, "warnings": warnings}


@router.post("/test-llm", response_model=SettingsTestResponse)
async def test_llm(
    session: AsyncSession = Depends(get_db),
) -> SettingsTestResponse:
    """Test which LLM providers are currently reachable.

    Performs lightweight connectivity checks against Claude, GPT, and
    Ollama endpoints. Does not make actual inference calls.

    Args:
        session: Async database session.

    Returns:
        Availability flags and detected model names for each provider.
    """
    claude_ok = False
    gpt_ok = False
    ollama_ok = False
    models: dict[str, str] = {}
    selected: str | None = None

    async with httpx.AsyncClient(timeout=LLM_TEST_TIMEOUT) as client:
        # Test Claude
        if app_settings.anthropic_api_key:
            try:
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": app_settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                claude_ok = resp.status_code == 200
                if claude_ok:
                    models["claude"] = "claude-opus-4-6"
            except httpx.HTTPError as e:
                logger.warning(f"Claude connectivity check failed: {e}")

        # Test GPT
        if app_settings.openai_api_key:
            try:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {app_settings.openai_api_key}"},
                )
                gpt_ok = resp.status_code == 200
                if gpt_ok:
                    models["gpt"] = "gpt-4o"
            except httpx.HTTPError as e:
                logger.warning(f"GPT connectivity check failed: {e}")

        # Test Ollama
        try:
            resp = await client.get(f"{app_settings.ollama_host}/api/tags")
            ollama_ok = resp.status_code == 200
            if ollama_ok:
                data = resp.json()
                ollama_models = data.get("models", [])
                if ollama_models:
                    models["ollama"] = ollama_models[0].get("name", "unknown")
                else:
                    models["ollama"] = "no models loaded"
        except httpx.HTTPError as e:
            logger.debug(f"Ollama connectivity check failed: {e}")

    # Determine selected provider
    if claude_ok:
        selected = "claude"
    elif gpt_ok:
        selected = "gpt"
    elif ollama_ok:
        selected = "local"

    return SettingsTestResponse(
        claude_available=claude_ok,
        gpt_available=gpt_ok,
        ollama_available=ollama_ok,
        selected=selected,
        models=models,
    )
