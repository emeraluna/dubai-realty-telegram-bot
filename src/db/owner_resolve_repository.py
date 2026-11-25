from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.enums import OwnerResolveStatus
from db.models import OwnerResolveJob


class OwnerResolveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(
        self,
        *,
        listing_id: int,
        requested_input: str,
        telegram_user_id: int | None = None,
        notify_chat_id: int | None = None,
        notify_message_id: int | None = None,
    ) -> OwnerResolveJob:
        settings = get_settings()
        deadline = datetime.now(UTC) + timedelta(hours=settings.owner_resolve_timeout_hours)
        job = OwnerResolveJob(
            listing_id=listing_id,
            requested_input=requested_input,
            status=OwnerResolveStatus.PENDING.value,
            telegram_user_id=telegram_user_id,
            notify_chat_id=notify_chat_id,
            notify_message_id=notify_message_id,
            deadline_at=deadline,
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def get(self, job_id: int) -> OwnerResolveJob | None:
        return await self._session.get(OwnerResolveJob, job_id)

    async def claim_next(self) -> OwnerResolveJob | None:
        now = datetime.now(UTC)
        stmt = (
            select(OwnerResolveJob)
            .where(
                OwnerResolveJob.status.in_(
                    (OwnerResolveStatus.PENDING.value, OwnerResolveStatus.RUNNING.value)
                ),
                OwnerResolveJob.deadline_at > now,
            )
            .order_by(OwnerResolveJob.created_at.asc())
            .limit(1)
        )
        bind = self._session.get_bind()
        if bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        result = await self._session.execute(stmt)
        job = result.scalar_one_or_none()
        if job is None:
            return None
        job.status = OwnerResolveStatus.RUNNING.value
        job.updated_at = now
        await self._session.flush()
        return job

    async def finish(
        self,
        job: OwnerResolveJob,
        *,
        status: OwnerResolveStatus,
        attempts: int,
        last_error: str | None = None,
    ) -> None:
        job.status = status.value
        job.attempts = attempts
        job.last_error = last_error
        job.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def find_active_for_listing(self, listing_id: int) -> OwnerResolveJob | None:
        stmt = (
            select(OwnerResolveJob)
            .where(
                OwnerResolveJob.listing_id == listing_id,
                OwnerResolveJob.status.in_(
                    (OwnerResolveStatus.PENDING.value, OwnerResolveStatus.RUNNING.value)
                ),
            )
            .order_by(OwnerResolveJob.id.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_stale_failed(self) -> int:
        now = datetime.now(UTC)
        stmt = (
            update(OwnerResolveJob)
            .where(
                OwnerResolveJob.status.in_(
                    (OwnerResolveStatus.PENDING.value, OwnerResolveStatus.RUNNING.value)
                ),
                OwnerResolveJob.deadline_at <= now,
            )
            .values(status=OwnerResolveStatus.FAILED.value, last_error="deadline_exceeded", updated_at=now)
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0