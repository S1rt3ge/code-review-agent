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
from backend.models.db_models import User
from backend.models.schemas import (
    SettingsResponse,
    SettingsTestResponse,
    SettingsUpdate,
)
from backend.utils.auth import get_current_user
from backend.utils.crypto import decrypt_value, encrypt_value
from backend.utils.database import get_db
from backend.utils.url_security import validate_server_http_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Known agent names accepted by the system.
VALID_AGENTS = {"security", "performance", "style", "logic"}
VALID_LM_PREFERENCES = {"auto", "claude", "gpt", "local"}

# Timeout for external LLM connectivity checks (seconds).
LLM_TEST_TIMEOUT = 10


def _try_decrypt(ciphertext: str | None) -> str | None:
    """Decrypt a ciphertext string, returning None when no value is configured."""
    if not ciphertext:
        return None
    try:
        return decrypt_value(ciphertext)
    except Exception as exc:
        raise RuntimeError("Configured API key could not be decrypted") from exc


def _private_ollama_allowed() -> bool:
    return (
        app_settings.app_env.lower() in {"development", "dev", "local", "test", "testing"}
        or app_settings.allow_private_ollama_hosts
    )


def _validate_ollama_host(host: str) -> str:
    return validate_server_http_url(host, allow_private=_private_ollama_allowed())


@router.get("", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
) -> SettingsResponse:
    """Return the current user's LLM and agent settings.

    Args:
        current_user: Authenticated user from JWT.

    Returns:
        Current settings. API keys are not returned — only whether they are set.
    """
    return SettingsResponse(
        plan=current_user.plan,
        api_key_claude_set=current_user.api_key_claude is not None,
        api_key_gpt_set=current_user.api_key_gpt is not None,
        ollama_enabled=current_user.ollama_enabled,
        ollama_host=current_user.ollama_host or app_settings.ollama_host,
        default_agents=current_user.default_agents or ["security", "performance", "style", "logic"],
        lm_preference=current_user.lm_preference or "auto",
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    payload: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Update user LLM settings and API keys.

    API keys are encrypted with Fernet before storage. Existing keys are
    preserved when the field is omitted (None) in the request.

    Args:
        payload: Fields to update (only non-None values are applied).
        current_user: Authenticated user from JWT.
        session: Async database session.

    Returns:
        Full updated settings response.

    Raises:
        HTTPException 400: If agent names or LLM preference are invalid.
    """
    warnings: list[str] = []

    # Validate agent names
    if payload.default_agents is not None:
        if not payload.default_agents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one default agent must be selected",
            )
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
            payload.ollama_host = _validate_ollama_host(payload.ollama_host)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        try:
            async with httpx.AsyncClient(timeout=LLM_TEST_TIMEOUT, follow_redirects=False) as client:
                resp = await client.get(f"{payload.ollama_host}/api/tags")
                if resp.status_code != 200:
                    warnings.append(f"Ollama host returned status {resp.status_code}")
        except httpx.HTTPError:
            warnings.append("Ollama host is unreachable")

    # Persist changes to the user record
    if payload.api_key_claude is not None:
        try:
            current_user.api_key_claude = encrypt_value(payload.api_key_claude)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Encryption is not configured on this server (FERNET_KEY missing). API key was not saved.",
            )

    if payload.api_key_gpt is not None:
        try:
            current_user.api_key_gpt = encrypt_value(payload.api_key_gpt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Encryption is not configured on this server (FERNET_KEY missing). API key was not saved.",
            )

    if payload.ollama_enabled is not None:
        current_user.ollama_enabled = payload.ollama_enabled

    if payload.ollama_host is not None:
        if payload.ollama_host:
            try:
                current_user.ollama_host = _validate_ollama_host(payload.ollama_host)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc
        else:
            current_user.ollama_host = None

    if payload.default_agents is not None:
        current_user.default_agents = payload.default_agents

    if payload.lm_preference is not None:
        current_user.lm_preference = payload.lm_preference

    # Re-attach to session (current_user came from a dependency session that
    # may be different from the route's session when both are injected).
    merged = await session.merge(current_user)
    await session.flush()

    logger.info("Settings updated for user %s", merged.email)
    return SettingsResponse(
        plan=merged.plan,
        api_key_claude_set=merged.api_key_claude is not None,
        api_key_gpt_set=merged.api_key_gpt is not None,
        ollama_enabled=merged.ollama_enabled,
        ollama_host=merged.ollama_host or app_settings.ollama_host,
        default_agents=merged.default_agents or ["security", "performance", "style", "logic"],
        lm_preference=merged.lm_preference or "auto",
        warnings=warnings,
    )


@router.post("/test-llm", response_model=SettingsTestResponse)
async def test_llm(
    current_user: User = Depends(get_current_user),
) -> SettingsTestResponse:
    """Test which LLM providers are currently reachable for this user.

    Resolves API keys from the user's stored settings (decrypted), falling
    back to application-level keys from environment variables.

    Args:
        current_user: Authenticated user from JWT.

    Returns:
        Availability flags and detected model names for each provider.
    """
    # Resolve effective API keys (user key overrides app-level key)
    try:
        claude_key = _try_decrypt(current_user.api_key_claude) or app_settings.anthropic_api_key
        gpt_key = _try_decrypt(current_user.api_key_gpt) or app_settings.openai_api_key
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    ollama_host = current_user.ollama_host or app_settings.ollama_host

    claude_ok = False
    gpt_ok = False
    ollama_ok = False
    models: dict[str, str] = {}
    selected: str | None = None

    async with httpx.AsyncClient(timeout=LLM_TEST_TIMEOUT, follow_redirects=False) as client:
        # Test Claude
        if claude_key:
            try:
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": claude_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                claude_ok = resp.status_code == 200
                if claude_ok:
                    models["claude"] = "claude-opus-4-6"
            except httpx.HTTPError as e:
                logger.warning("Claude connectivity check failed: %s", e)

        # Test GPT
        if gpt_key:
            try:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {gpt_key}"},
                )
                gpt_ok = resp.status_code == 200
                if gpt_ok:
                    models["gpt"] = "gpt-4o"
            except httpx.HTTPError as e:
                logger.warning("GPT connectivity check failed: %s", e)

        # Test Ollama only when the user explicitly enabled local models.
        if current_user.ollama_enabled:
            try:
                ollama_host = _validate_ollama_host(ollama_host)
                resp = await client.get(f"{ollama_host}/api/tags")
                ollama_ok = resp.status_code == 200
                if ollama_ok:
                    data = resp.json()
                    ollama_models = data.get("models", [])
                    models["ollama"] = (
                        ollama_models[0].get("name", "unknown") if ollama_models else "no models loaded"
                    )
            except (ValueError, httpx.HTTPError) as e:
                logger.debug("Ollama connectivity check failed: %s", e)

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
