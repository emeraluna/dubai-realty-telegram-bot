from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import get_settings
from db.base import Base
from db.enums import ImportRowAction, OwnerSource
from db.import_repository import ImportRepository
from db.models import ImportBatch, ImportRow, Listing
from db.repository import ListingRepository
from importers.mapping import map_headers
from importers.owner_importer import ImportFileError, import_owner_file


@pytest.fixture
async def import_db(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    get_settings.cache_clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from db import session as db_session_mod

    monkeypatch.setattr(db_session_mod, "_engine", engine)
    monkeypatch.setattr(db_session_mod, "_session_factory", factory)

    yield factory
    get_settings.cache_clear()
    await engine.dispose()
    db_session_mod._engine = None
    db_session_mod._session_factory = None


@pytest.mark.asyncio
async def test_csv_happy_path(import_db, tmp_path: Path) -> None:
    csv_path = tmp_path / "owners.csv"
    csv_path.write_text(
        "permit,owner name,phone,unit,building\n"
        "7111111111111,CSV Owner,+971501111111,101,Alpha Tower\n",
        encoding="utf-8",
    )
    result = await import_owner_file(csv_path, admin_user_id=1)
    assert result.rows_inserted == 1
    assert result.rows_errored == 0

    async with import_db() as session:
        batch = await session.get(ImportBatch, result.batch_id)
        assert batch is not None
        assert batch.rows_total == 1
        row_count = len(
            list((await session.execute(select(ImportRow).where(ImportRow.batch_id == result.batch_id))).scalars())
        )
        assert row_count == 1

        listing = await ListingRepository(session, cache_ttl_days=30).get_by_permit("7111111111111")
        assert listing is not None
        assert listing.owner_name == "CSV Owner"
        assert listing.owner_source == OwnerSource.MANUAL.value


@pytest.mark.asyncio
async def test_xlsx_happy_path(import_db, tmp_path: Path) -> None:
    xlsx_path = tmp_path / "owners.xlsx"
    df = pd.DataFrame(
        [
            {
                "permit": "7222222222222",
                "owner name": "XLSX Owner",
                "phone": "+971502222222",
                "unit": "202",
                "building": "Beta Tower",
            }
        ]
    )
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    result = await import_owner_file(xlsx_path, admin_user_id=2)
    assert result.rows_inserted == 1


@pytest.mark.asyncio
async def test_alias_header_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    get_settings.cache_clear()
    headers = ["Trakheesi No", "Landlord", "Mobile"]
    mapping, _ = map_headers(headers)
    assert mapping["Trakheesi No"] == "permit_number"
    assert mapping["Landlord"] == "owner_name"
    assert mapping["Mobile"] == "owner_phone"


@pytest.mark.asyncio
async def test_fuzzy_mapping_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("IMPORT_FUZZY_THRESHOLD", "80")
    get_settings.cache_clear()
    headers = ["permit", "permit no", "owner"]
    _, warnings = map_headers(headers)
    assert warnings


@pytest.mark.asyncio
async def test_blank_cell_does_not_delete_manual(import_db, tmp_path: Path) -> None:
    csv1 = tmp_path / "one.csv"
    csv1.write_text("permit,owner name,phone\n7333333333333,Keep Me,+971503333333\n", encoding="utf-8")
    await import_owner_file(csv1, admin_user_id=3)
    csv2 = tmp_path / "two.csv"
    csv2.write_text("permit,owner name,phone\n7333333333333,,\n", encoding="utf-8")
    result = await import_owner_file(csv2, admin_user_id=3)
    assert result.rows_skipped >= 0
    async with import_db() as session:
        listing = await ListingRepository(session, cache_ttl_days=30).get_by_permit("7333333333333")
        assert listing is not None
        assert listing.owner_name == "Keep Me"
        assert listing.owner_phone == "+971503333333"


@pytest.mark.asyncio
async def test_unmatched_row_creates_manual_listing(import_db, tmp_path: Path) -> None:
    path = tmp_path / "new.csv"
    path.write_text(
        "owner name,phone,unit,building\nNew Manual,+971504444444,303,Gamma\n",
        encoding="utf-8",
    )
    result = await import_owner_file(path, admin_user_id=4)
    assert result.rows_inserted == 1
    async with import_db() as session:
        listing = await ListingRepository(session, cache_ttl_days=30).get_by_unit_and_building("303", "Gamma")
        assert listing is not None
        assert listing.source == "manual"
        assert listing.owner_source == OwnerSource.MANUAL.value


@pytest.mark.asyncio
async def test_bad_row_recorded_batch_continues(import_db, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "mixed.csv"
    path.write_text(
        "permit,owner name,phone\n"
        "7444444444444,Good,+971505555555\n"
        "7555666777888,Bad,+971506666666\n",
        encoding="utf-8",
    )
    from db.repository import ListingRepository

    original = ListingRepository.upsert_manual_owner
    calls = {"n": 0}

    async def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("forced row failure")
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(ListingRepository, "upsert_manual_owner", flaky)
    result = await import_owner_file(path, admin_user_id=5)
    assert result.rows_total == 2
    assert result.rows_errored == 1
    assert result.rows_inserted == 1
    async with import_db() as session:
        stmt = select(ImportRow).where(ImportRow.batch_id == result.batch_id)
        rows = list((await session.execute(stmt)).scalars().all())
        assert len(rows) == 2
        assert any(r.action == ImportRowAction.ERROR.value for r in rows)


@pytest.mark.asyncio
async def test_reimport_idempotent(import_db, tmp_path: Path) -> None:
    path = tmp_path / "idem.csv"
    path.write_text(
        "permit,owner name,phone\n7555555555555,Idem Owner,+971507777777\n",
        encoding="utf-8",
    )
    first = await import_owner_file(path, admin_user_id=6)
    second = await import_owner_file(path, admin_user_id=6)
    assert first.rows_inserted == 1
    assert second.rows_inserted == 0
    async with import_db() as session:
        listings = list((await session.execute(select(Listing))).scalars().all())
        permits = [x for x in listings if x.permit_number == "7555555555555"]
        assert len(permits) == 1
        assert permits[0].owner_phone == "+971507777777"


@pytest.mark.asyncio
async def test_empty_file_raises(import_db, tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("owner,phone\n", encoding="utf-8")
    with pytest.raises(ImportFileError):
        await import_owner_file(path, admin_user_id=1)