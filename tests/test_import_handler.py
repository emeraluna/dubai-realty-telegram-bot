from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import import_handler


@pytest.mark.asyncio
async def test_cmd_import_denies_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("IMPORT_ADMIN_IDS", "1001")
    from config.settings import get_settings

    get_settings.cache_clear()

    message = MagicMock()
    message.from_user = MagicMock(id=999)
    message.answer = AsyncMock()
    await import_handler.cmd_import(message)
    message.answer.assert_awaited_once()
    assert "restricted" in message.answer.await_args.args[0].lower()


@pytest.mark.asyncio
async def test_document_ignored_for_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("IMPORT_ADMIN_IDS", "1001")
    from config.settings import get_settings

    get_settings.cache_clear()

    message = MagicMock()
    message.from_user = MagicMock(id=999)
    message.document = MagicMock(file_name="owners.csv", file_id="f1")
    message.bot = MagicMock()

    with patch.object(import_handler, "import_owner_file", AsyncMock()) as mock_import:
        await import_handler.handle_import_document(message)
        mock_import.assert_not_called()


@pytest.mark.asyncio
async def test_document_wrong_extension_not_imported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("IMPORT_ADMIN_IDS", "1001")
    from config.settings import get_settings

    get_settings.cache_clear()

    message = MagicMock()
    message.from_user = MagicMock(id=1001)
    message.document = MagicMock(file_name="owners.pdf", file_id="f1")
    message.bot = MagicMock()

    with patch.object(import_handler, "import_owner_file", AsyncMock()) as mock_import:
        await import_handler.handle_import_document(message)
        mock_import.assert_not_called()


@pytest.mark.asyncio
async def test_error_report_callback_builds_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import asynccontextmanager

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("IMPORT_ADMIN_IDS", "1001")
    from config.settings import get_settings

    get_settings.cache_clear()

    fake_row = MagicMock(row_index=1, error="x", raw_row={"a": "b"})
    callback = MagicMock()
    callback.from_user = MagicMock(id=1001)
    callback.data = "import_err:42"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.answer_document = AsyncMock()

    repo = MagicMock()
    repo.error_rows = AsyncMock(return_value=[fake_row])

    @asynccontextmanager
    async def fake_scope():
        yield MagicMock()

    with patch.object(import_handler, "session_scope", fake_scope):
        with patch.object(import_handler, "ImportRepository", return_value=repo):
            with patch.object(import_handler, "build_error_report_csv", return_value=b"csv-bytes") as build:
                await import_handler.on_import_error_report(callback)
                build.assert_called_once_with([fake_row])
                callback.message.answer_document.assert_awaited_once()
                doc = callback.message.answer_document.await_args.args[0]
                assert doc.filename == "import_errors_42.csv"