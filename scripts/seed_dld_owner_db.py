"""Create a local SQLite DLD owner mirror for development (operator-owned data)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "dld_owners.sqlite"


async def main() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    DB.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite+aiosqlite:///{DB.as_posix()}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP TABLE IF EXISTS property_owners")
        await conn.exec_driver_sql(
            """
            CREATE TABLE property_owners (
                permit_number TEXT,
                ad_license TEXT,
                transaction_number TEXT,
                listing_guid TEXT,
                unit_number TEXT,
                building_name TEXT,
                pf_listing_id TEXT,
                real_estate_number TEXT,
                owner_name TEXT,
                owner_phone TEXT
            )
            """
        )
        await conn.exec_driver_sql(
            """
            INSERT INTO property_owners VALUES (
                NULL, '1106530', '153343',
                'qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme',
                NULL, 'Binghatti Grove', '168788844', '32071',
                NULL, NULL
            )
            """
        )
    await engine.dispose()
    print(f"Seeded {DB}")
    print(f"Set DLD_OWNER_DATABASE_URL={url}")


if __name__ == "__main__":
    asyncio.run(main())
    raise SystemExit(0)