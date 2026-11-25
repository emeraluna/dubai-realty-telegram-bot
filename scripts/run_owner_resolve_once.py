"""One-shot owner resolve for Binghatti listing (no 5h loop)."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(ROOT / 'data' / 'realty.db').as_posix()}"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "t")
os.environ.setdefault("APIFY_TOKEN", "a")
os.environ.setdefault("SCRAPEFORGE_KEY", "s")
os.environ.setdefault("MADMOUN_PLAYWRIGHT_ENABLED", "false")
dld_db = ROOT / "data" / "dld_owners.sqlite"
if dld_db.is_file():
    os.environ["DLD_OWNER_DATABASE_URL"] = f"sqlite+aiosqlite:///{dld_db.as_posix()}"


async def main() -> int:
    from config.settings import get_settings
    from db.repository import ListingRepository
    from db.schemas import ListingUpsertPayload
    from db.session import session_scope
    from db.enums import OwnerSource
    from services.owner_broker_guard import owner_matches_broker, strip_broker_owner
    from services.owner_source_attempts import owner_complete, run_owner_source_cycle

    get_settings.cache_clear()
    async with session_scope() as session:
        repo = ListingRepository(session, cache_ttl_days=get_settings().cache_ttl_days)
        listing = await repo.get_by_id(1)
        if listing is None:
            print("no listing id=1")
            return 1
        if listing.owner_name and str(listing.owner_name).startswith("REPLACE_"):
            await repo.upsert_from_payload(
                ListingUpsertPayload(
                    source=listing.source,
                    source_listing_id=listing.source_listing_id,
                    owner_name=None,
                    owner_phone=None,
                )
            )
            listing = await repo.get_by_id(1)
        assert listing is not None
        if owner_matches_broker(listing.owner_name, listing.owner_phone, raw_payload=listing.raw_payload):
            await repo.upsert_from_payload(
                ListingUpsertPayload(
                    source=listing.source,
                    source_listing_id=listing.source_listing_id,
                    owner_name=None,
                    owner_phone=None,
                )
            )
            listing = await repo.get_by_id(1)
            assert listing is not None
        patch = await run_owner_source_cycle(repo, listing)
        if patch:
            await repo.upsert_from_payload(
                ListingUpsertPayload(
                    source=listing.source,
                    source_url=listing.source_url,
                    source_listing_id=listing.source_listing_id,
                    unit_number=patch.unit_number,
                    building=patch.building,
                    permit_number=patch.permit_number,
                    owner_name=patch.owner_name,
                    owner_phone=patch.owner_phone,
                    raw_payload=patch.raw_payload or {},
                )
            )
            listing = await repo.get_by_id(1)
        assert listing is not None
        ok = owner_complete(
            type(
                "P",
                (),
                {
                    "owner_name": listing.owner_name,
                    "owner_phone": listing.owner_phone,
                },
            )()
        )
        print("owner_name", listing.owner_name)
        print("owner_phone", listing.owner_phone)
        print("owner_source", listing.owner_source)
        print("complete", ok)
        broker = (listing.raw_payload or {}).get("trakheesi_integration", {}).get("broker")
        if broker:
            print("broker_on_file", broker.get("broker_name_en"), broker.get("broker_phone"))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))