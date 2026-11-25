from __future__ import annotations

import asyncio

import structlog
from aiogram import Bot

from bot.formatters import format_listing_html
from bot.keyboards import listing_actions_keyboard
from config import get_settings
from db.enums import OwnerResolveStatus
from db.owner_resolve_repository import OwnerResolveRepository
from db.repository import ListingRepository
from db.session import session_scope
from services.owner_resolve_pipeline import resolve_owner_for_listing

log = structlog.get_logger(__name__)


async def _notify(bot: Bot, chat_id: int, message_id: int, listing, *, cache_hit: bool = False) -> None:
    body = format_listing_html(listing, cache_hit=cache_hit)
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=body,
        parse_mode="HTML",
        reply_markup=listing_actions_keyboard(listing.id),
    )


async def _run_job(bot: Bot, job_id: int) -> None:
    async with session_scope() as session:
        jobs = OwnerResolveRepository(session)
        listings = ListingRepository(session, cache_ttl_days=get_settings().cache_ttl_days)
        job = await jobs.get(job_id)
        if job is None:
            return
        try:
            outcome = await resolve_owner_for_listing(
                listings,
                listing_id=job.listing_id,
                requested_input=job.requested_input,
                deadline=job.deadline_at,
            )
        except Exception as exc:
            log.exception("owner_resolve.job_failed", job_id=job_id, error=str(exc))
            await jobs.finish(
                job,
                status=OwnerResolveStatus.FAILED,
                attempts=job.attempts,
                last_error=str(exc),
            )
            return

        status = OwnerResolveStatus.SUCCEEDED if outcome.success else OwnerResolveStatus.FAILED
        await jobs.finish(job, status=status, attempts=outcome.attempts, last_error=None if outcome.success else outcome.message)

        if job.notify_chat_id and job.notify_message_id and outcome.listing is not None:
            try:
                await _notify(bot, job.notify_chat_id, job.notify_message_id, outcome.listing)
            except Exception as exc:
                log.warning("owner_resolve.notify_failed", job_id=job_id, error=str(exc))


async def _worker_loop(bot: Bot) -> None:
    settings = get_settings()
    if not settings.owner_resolve_enabled:
        return
    while True:
        try:
            async with session_scope() as session:
                jobs_repo = OwnerResolveRepository(session)
                await jobs_repo.mark_stale_failed()
                job = await jobs_repo.claim_next()
                if job is None:
                    await asyncio.sleep(15)
                    continue
                job_id = job.id
            asyncio.create_task(_run_job(bot, job_id))
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("owner_resolve.worker_error", error=str(exc))
            await asyncio.sleep(30)


def start_owner_resolve_worker(bot: Bot) -> asyncio.Task[None]:
    return asyncio.create_task(_worker_loop(bot))


async def enqueue_owner_resolve(
    *,
    listing_id: int,
    requested_input: str,
    telegram_user_id: int,
    notify_chat_id: int,
    notify_message_id: int,
) -> bool:
    settings = get_settings()
    if not settings.owner_resolve_enabled:
        return False
    async with session_scope() as session:
        jobs = OwnerResolveRepository(session)
        existing = await jobs.find_active_for_listing(listing_id)
        if existing is not None:
            return False
        await jobs.create_job(
            listing_id=listing_id,
            requested_input=requested_input,
            telegram_user_id=telegram_user_id,
            notify_chat_id=notify_chat_id,
            notify_message_id=notify_message_id,
        )
    return True