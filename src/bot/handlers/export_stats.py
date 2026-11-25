from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from bot.services.export_csv import listings_to_csv_bytes
from config import get_settings
from db.repository import ListingRepository
from db.session import session_scope

router = Router(name="export_stats")


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    assert message.from_user is not None
    async with session_scope() as session:
        settings = get_settings()
        repo = ListingRepository(session, cache_ttl_days=settings.cache_ttl_days)
        listings = await repo.listings_for_user_export(message.from_user.id)

    if not listings:
        await message.answer("No archived listings for your account yet.")
        return

    data = listings_to_csv_bytes(listings)
    file = BufferedInputFile(data, filename="realty_archive.csv")
    await message.answer_document(file, caption=f"Exported {len(listings)} record(s).")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    assert message.from_user is not None
    async with session_scope() as session:
        settings = get_settings()
        repo = ListingRepository(session, cache_ttl_days=settings.cache_ttl_days)
        stats = await repo.user_stats(message.from_user.id)

    miss = stats["lookups_total"] - stats["cache_hits"]
    await message.answer(
        "<b>Your stats</b>\n"
        f"Lookups: {stats['lookups_total']}\n"
        f"Cache hits: {stats['cache_hits']}\n"
        f"Fresh extractions: {miss}\n"
        f"Listings archived: {stats['listings_archived']}\n"
        f"Savings (extractions avoided): {stats['extractions_saved']}",
        parse_mode="HTML",
    )