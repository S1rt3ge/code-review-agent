"""Tests for startup recovery of stuck reviews."""

import uuid

import pytest
from sqlalchemy import insert, select

from backend.models.db_models import Repository, Review, User
from backend.services.recovery import recover_stuck_reviews
from backend.utils.auth import hash_password
from backend.utils.database import async_session_factory


@pytest.mark.integration
@pytest.mark.asyncio
async def test_recover_stuck_reviews_marks_analyzing_as_error() -> None:
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    stuck_review_id = uuid.uuid4()
    done_review_id = uuid.uuid4()

    async with async_session_factory() as session:
        await session.execute(
            insert(User).values(
                id=user_id,
                email=f"recover_{uuid.uuid4().hex[:8]}@test.com",
                username=f"recover_{uuid.uuid4().hex[:8]}",
                hashed_password=hash_password("TestPass123!"),
            )
        )
        await session.execute(
            insert(Repository).values(
                id=repo_id,
                user_id=user_id,
                github_repo_owner="testorg",
                github_repo_name=f"repo_{uuid.uuid4().hex[:6]}",
                github_repo_url="https://github.com/testorg/recovery",
                enabled=True,
            )
        )
        await session.execute(
            insert(Review).values(
                id=stuck_review_id,
                user_id=user_id,
                repo_id=repo_id,
                github_pr_number=101,
                status="analyzing",
            )
        )
        await session.execute(
            insert(Review).values(
                id=done_review_id,
                user_id=user_id,
                repo_id=repo_id,
                github_pr_number=102,
                status="done",
            )
        )
        await session.commit()

    async with async_session_factory() as session:
        changed = await recover_stuck_reviews(session)
        await session.commit()
        assert changed >= 1

    async with async_session_factory() as session:
        stuck_review = await session.scalar(
            select(Review).where(Review.id == stuck_review_id)
        )
        done_review = await session.scalar(
            select(Review).where(Review.id == done_review_id)
        )

        assert stuck_review is not None
        assert stuck_review.status == "error"
        assert stuck_review.error_message == "Analysis interrupted by server restart"
        assert stuck_review.completed_at is not None

        assert done_review is not None
        assert done_review.status == "done"
