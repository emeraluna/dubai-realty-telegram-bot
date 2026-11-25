from __future__ import annotations

import html

import structlog
from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from bot.formatters import format_listing_html
from bot.keyboards import listing_actions_keyboard
from bot.services.lookup_orchestrator import InputParseError, LookupOrchestrator
from bot.services.owner_resolve_worker import enqueue_owner_resolve
from config import get_settings
from db.enums import OwnerSource
from scrapers.errors import ExtractionError

log = structlog.get_logger(__name__)

router = Router(name="lookup")
router.message.filter(F.chat.type == ChatType.PRIVATE)
_orchestrator = LookupOrchestrator()


@router.message(F.text & ~F.text.startswith("/"))
async def handle_lookup_text(message: Message) -> None:
    assert message.from_user is not None
    text = message.text or ""
    status = await message.answer("searching…", parse_mode="HTML")

    try:
        outcome = await _orchestrator.run(
            telegram_user_id=message.from_user.id,
            text=text,
            force_refresh=False,
        )
    except InputParseError:
        await status.edit_text("Could not parse input. Send a PF/Bayut URL or Trakheesi permit.")
        return
    except ExtractionError as exc:
        log.warning("lookup.extract_failed", error=str(exc))
        await status.edit_text(f"Lookup failed: {html.escape(str(exc))}", parse_mode="HTML")
        return
    except Exception as exc:
        log.exception("lookup.unexpected", error=str(exc))
        await status.edit_text("Lookup failed due to an internal error.")
        return

    body = format_listing_html(outcome.listing, cache_hit=outcome.cache_hit)
    listing = outcome.listing
    settings = get_settings()
    missing_owner = not (listing.owner_name and listing.owner_phone)
    if (
        settings.owner_resolve_enabled
        and missing_owner
        and listing.owner_source != OwnerSource.MANUAL.value
    ):
        queued = await enqueue_owner_resolve(
            listing_id=listing.id,
            requested_input=text,
            telegram_user_id=message.from_user.id,
            notify_chat_id=message.chat.id,
            notify_message_id=status.message_id,
        )
        if queued:
            body = f"{body}\n\n<i>Owner auto-resolve running (up to {int(settings.owner_resolve_timeout_hours)}h)…</i>"

    await status.edit_text(
        body,
        parse_mode="HTML",
        reply_markup=listing_actions_keyboard(listing.id),
    )