from __future__ import annotations

import csv
import html
import io

import structlog
from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery

from bot.formatters import format_listing_html
from bot.keyboards import listing_actions_keyboard
from bot.services.export_csv import CSV_HEADERS, listing_to_row
from bot.services.lookup_orchestrator import LookupOrchestrator
from config import get_settings
from db.repository import ListingRepository
from db.session import session_scope
from scrapers.errors import ExtractionError

log = structlog.get_logger(__name__)

router = Router(name="callbacks")
_orchestrator = LookupOrchestrator()


@router.callback_query(F.data.startswith("refresh:"))
async def on_refresh(callback: CallbackQuery) -> None:
    assert callback.from_user is not None
    assert callback.message is not None
    listing_id = int((callback.data or "").split(":", 1)[1])

    async with session_scope() as session:
        settings = get_settings()
        repo = ListingRepository(session, cache_ttl_days=settings.cache_ttl_days)
        listing = await repo.get_by_id(listing_id)
        if listing is None:
            await callback.answer("Listing not found.", show_alert=True)
            return
        if listing.source == "trakheesi":
            refresh_text = listing.permit_number or str(listing.id)
        else:
            refresh_text = listing.source_url or f"{listing.source}:{listing.source_listing_id}"

    await callback.answer()
    status = await callback.message.edit_text("searching…", parse_mode="HTML")

    try:
        outcome = await _orchestrator.run(
            telegram_user_id=callback.from_user.id,
            text=refresh_text,
            force_refresh=True,
        )
    except ExtractionError as exc:
        await status.edit_text(html.escape(str(exc)), parse_mode="HTML")
        return
    except Exception as exc:
        log.exception("refresh.failed", error=str(exc))
        await status.edit_text("Refresh failed.")
        return

    body = format_listing_html(outcome.listing, cache_hit=outcome.cache_hit)
    await status.edit_text(
        body,
        parse_mode="HTML",
        reply_markup=listing_actions_keyboard(outcome.listing.id),
    )


@router.callback_query(F.data.startswith("export_one:"))
async def on_export_one(callback: CallbackQuery) -> None:
    assert callback.message is not None
    listing_id = int((callback.data or "").split(":", 1)[1])

    async with session_scope() as session:
        settings = get_settings()
        repo = ListingRepository(session, cache_ttl_days=settings.cache_ttl_days)
        listing = await repo.get_by_id(listing_id)

    if listing is None:
        await callback.answer("Listing not found.", show_alert=True)
        return

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS)
    writer.writerow(listing_to_row(listing))
    data = buffer.getvalue().encode("utf-8-sig")
    file = BufferedInputFile(data, filename=f"listing_{listing_id}.csv")
    await callback.answer()
    await callback.message.answer_document(file, caption=f"Listing #{listing_id}")