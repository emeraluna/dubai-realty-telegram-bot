from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from services.dld_owner_database import fetch_owner_from_dld_database


@pytest.fixture
def owner_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "dld_owners.db"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("DLD_OWNER_DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("DLD_OWNER_TABLE", "property_owners")
    from config.settings import get_settings
    from services import dld_owner_database as mod

    get_settings.cache_clear()
    mod._owner_engine.cache_clear()

    import asyncio

    async def _init() -> None:
        engine = create_async_engine(get_settings().dld_owner_database_url)
        async with engine.begin() as conn:
            await conn.exec_driver_sql(
                """
                CREATE TABLE property_owners (
                    permit_number TEXT,
                    ad_license TEXT,
                    transaction_number TEXT,
                    owner_name TEXT,
                    owner_phone TEXT
                )
                """
            )
            await conn.exec_driver_sql(
                "INSERT INTO property_owners VALUES ('7123456789012', '1106530', '153343', 'Unit Owner', '+971501112233')"
            )
        await engine.dispose()

    asyncio.run(_init())


@pytest.mark.asyncio
async def test_fetch_owner_from_dld_database_by_ad_license(owner_db: None) -> None:
    from config.settings import get_settings

    get_settings.cache_clear()
    payload = await fetch_owner_from_dld_database(
        {"permit_number": "1106530", "transaction_number": None, "listing_guid": None}
    )
    assert payload.owner_name == "Unit Owner"
    assert payload.owner_phone == "+971501112233"