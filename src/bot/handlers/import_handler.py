from __future__ import annotations

import tempfile
from pathlib import Path

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from config import get_settings
from db.import_repository import ImportRepository
from db.session import session_scope
from importers.csv_report import build_error_report_csv
from importers.owner_importer import ImportFileError, import_owner_file

log = structlog.get_logger(__name__)

router = Router(name="import_owner")

IMPORT_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def _import_admins_configured() -> bool:
    return bool(get_settings().import_admin_ids)


def _is_import_admin(user_id: int) -> bool:
    settings = get_settings()
    admins = settings.import_admin_ids
    return bool(admins) and user_id in admins


@router.message(Command("import"))
async def cmd_import(message: Message) -> None:
    if not _import_admins_configured():
        await message.answer("Import is disabled: set IMPORT_ADMIN_IDS in configuration.")
        return
    if not message.from_user or not _is_import_admin(message.from_user.id):
        await message.answer("Import is restricted to import admins.")
        return
    await message.answer("Send me a .csv, .xlsx, or .xls owner file.")


@router.message(Command("imports"))
async def cmd_imports(message: Message) -> None:
    if not _import_admins_configured():
        await message.answer("Import is disabled: set IMPORT_ADMIN_IDS in configuration.")
        return
    if not message.from_user or not _is_import_admin(message.from_user.id):
        await message.answer("Import is restricted to import admins.")
        return

    async with session_scope() as session:
        repo = ImportRepository(session)
        batches = await repo.recent_batches(limit=10)

    if not batches:
        await message.answer("No import batches yet.")
        return

    lines = ["<b>Recent imports</b>"]
    for batch in batches:
        lines.append(
            f"#{batch.id} {batch.filename}: total={batch.rows_total} "
            f"ins={batch.rows_inserted} upd={batch.rows_updated} "
            f"skip={batch.rows_skipped} err={batch.rows_errored}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.document)
async def handle_import_document(message: Message) -> None:
    if not message.from_user or not message.document:
        return
    if not _import_admins_configured():
        return
    if not _is_import_admin(message.from_user.id):
        return

    name = message.document.file_name or ""
    suffix = Path(name).suffix.lower()
    if suffix not in IMPORT_EXTENSIONS:
        return

    assert message.bot is not None
    file = await message.bot.get_file(message.document.file_id)
    assert file.file_path is not None

    with tempfile.NamedTemporaryFile(delete=True, suffix=suffix) as tmp:
        await message.bot.download_file(file.file_path, tmp.name)
        data = Path(tmp.name).read_bytes()

    try:
        result = await import_owner_file(
            data,
            filename=name,
            admin_user_id=message.from_user.id,
        )
    except ImportFileError as exc:
        await message.answer(f"Import failed: {exc}")
        return
    except Exception as exc:
        log.exception("import.failed", error=str(exc))
        await message.answer("Import failed due to an internal error.")
        return

    reply = result.summary_line()
    if result.rows_errored > 0:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Download error report", callback_data=f"import_err:{result.batch_id}")]
            ]
        )
        await message.answer(reply, reply_markup=kb)
    else:
        await message.answer(reply)


@router.callback_query(F.data.startswith("import_err:"))
async def on_import_error_report(callback: CallbackQuery) -> None:
    if not callback.from_user or not _is_import_admin(callback.from_user.id):
        await callback.answer("Not allowed.", show_alert=True)
        return
    batch_id = int((callback.data or "").split(":", 1)[1])
    async with session_scope() as session:
        repo = ImportRepository(session)
        rows = await repo.error_rows(batch_id)
        if not rows:
            await callback.answer("No errors in batch.", show_alert=True)
            return
        data = build_error_report_csv(rows)
    assert callback.message is not None
    file = BufferedInputFile(data, filename=f"import_errors_{batch_id}.csv")
    await callback.answer()
    await callback.message.answer_document(file, caption=f"Import #{batch_id} errors")