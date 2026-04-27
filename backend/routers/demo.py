"""Demo mode endpoints for local self-hosted demos."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.db_models import User
from backend.models.schemas import DemoSeedResponse
from backend.services.demo_seed import is_demo_seed_allowed, seed_demo_data
from backend.utils.auth import get_current_user
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/seed", response_model=DemoSeedResponse)
async def seed_demo(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DemoSeedResponse:
    """Load deterministic demo data for the authenticated user."""
    if not is_demo_seed_allowed(settings.app_env):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo data can only be loaded in local development or demo environments",
        )

    result = await seed_demo_data(session=session, user_id=current_user.id)
    logger.info("Seeded demo data for user %s", current_user.id)
    return DemoSeedResponse.model_validate(result)
