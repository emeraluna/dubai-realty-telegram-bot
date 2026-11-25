"""Extract + owner-resolve for a single Property Finder URL."""
from __future__ import annotations

import argparse
import asyncio
import json
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
    os.environ.setdefault("DLD_OWNER_DATABASE_URL", f"sqlite+aiosqlite:///{dld_db.as_posix()}")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    url = args.url.strip()

    from config.settings import get_settings
    from db.repository import ListingRepository
    from db.schemas import ListingUpsertPayload
    from db.session import session_scope
    from scrapers.chain import ExtractorChain
    from services.input_parser import parse_lookup_input
    from services.owner_broker_guard import broker_contact_from_payload
    from services.owner_source_attempts import owner_complete, run_owner_source_cycle

    get_settings.cache_clear()
    req = parse_lookup_input(url)
    payload = await ExtractorChain().extract(req)

    async with session_scope() as session:
        repo = ListingRepository(session, cache_ttl_days=get_settings().cache_ttl_days)
        await repo.upsert_from_payload(payload.to_upsert(req))
        listing = await repo.get_by_source_id(req.source, req.external_id)
        if listing is None:
            print("upsert failed")
            return 1
        patch = await run_owner_source_cycle(repo, listing)
        if patch:
            await repo.upsert_from_payload(
                ListingUpsertPayload(
                    source=listing.source,
                    source_url=listing.source_url or url,
                    source_listing_id=listing.source_listing_id,
                    unit_number=patch.unit_number or listing.unit_number,
                    building=patch.building or listing.building,
                    community=patch.community or listing.community,
                    developer=patch.developer or listing.developer,
                    size_sqft=patch.size_sqft or listing.size_sqft,
                    plot_number=patch.plot_number,
                    permit_number=patch.permit_number or listing.permit_number,
                    permit_status=patch.permit_status,
                    owner_name=patch.owner_name,
                    owner_phone=patch.owner_phone,
                    raw_payload=patch.raw_payload or listing.raw_payload or {},
                )
            )
            listing = await repo.get_by_source_id(req.source, req.external_id)
        assert listing is not None

    broker = broker_contact_from_payload(listing.raw_payload or {})
    out = {
        "listing_id": listing.id,
        "source_listing_id": listing.source_listing_id,
        "building": listing.building,
        "permit_number": listing.permit_number,
        "owner_name": listing.owner_name,
        "owner_phone": listing.owner_phone,
        "owner_source": listing.owner_source,
        "complete": owner_complete(
            type("P", (), {"owner_name": listing.owner_name, "owner_phone": listing.owner_phone})()
        ),
        "broker_name": broker[0],
        "broker_phone": broker[1],
        "validation_url": (listing.raw_payload or {}).get("direct", {}).get("permit_validation_url"),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))