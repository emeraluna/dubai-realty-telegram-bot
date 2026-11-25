from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _postgres_reachable(url: str) -> bool:
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        async def probe() -> bool:
            engine = create_async_engine(url, pool_pre_ping=True)
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                return True
            finally:
                await engine.dispose()

        return asyncio.run(probe())
    except Exception:
        return False


@pytest.mark.integration
def test_alembic_0002_upgrade_downgrade_preserves_listings(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.getenv(
        "MIGRATION_TEST_DATABASE_URL",
        "postgresql+asyncpg://realty:realty@127.0.0.1:5432/realty",
    )
    if not _postgres_reachable(url):
        pytest.skip("PostgreSQL not available for migration round-trip test")

    env = os.environ.copy()
    env.update(
        {
            "TELEGRAM_BOT_TOKEN": "t",
            "APIFY_TOKEN": "a",
            "SCRAPEFORGE_KEY": "s",
            "DATABASE_URL": url,
        }
    )

    def alembic(*args: str) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(f"alembic {' '.join(args)} failed:\n{proc.stderr}\n{proc.stdout}")

    async def seed_listing() -> str:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        permit = "7999999999999"
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM listings WHERE permit_number = :p"), {"p": permit})
            await conn.execute(
                text(
                    """
                    INSERT INTO listings (
                        source, permit_number, owner_name, owner_phone, raw_payload
                    ) VALUES (
                        'bayut', :permit, 'Roundtrip Owner', '+971509999999', '{}'::jsonb
                    )
                    """
                ),
                {"permit": permit},
            )
        await engine.dispose()
        return permit

    async def assert_listing(permit: str) -> None:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(url)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT owner_name, owner_phone FROM listings WHERE permit_number = :p"),
                {"p": permit},
            )
            row = result.one()
        await engine.dispose()
        assert row.owner_name == "Roundtrip Owner"
        assert row.owner_phone == "+971509999999"

    alembic("upgrade", "20241124_0001")
    permit = asyncio.run(seed_listing())
    alembic("upgrade", "head")
    asyncio.run(assert_listing(permit))
    alembic("downgrade", "20241124_0001")
    asyncio.run(assert_listing(permit))
    alembic("upgrade", "head")
    asyncio.run(assert_listing(permit))