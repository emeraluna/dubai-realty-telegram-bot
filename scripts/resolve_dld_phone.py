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
dld_db = ROOT / "data" / "dld_owners.sqlite"
if dld_db.is_file():
    os.environ.setdefault("DLD_OWNER_DATABASE_URL", f"sqlite+aiosqlite:///{dld_db.as_posix()}")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phone")
    args = parser.parse_args()

    from config.settings import get_settings
    from db.repository import ListingRepository
    from db.session import session_scope
    from services.input_parser import parse_lookup_input
    from services.owner_phone_lookup import resolve_owner_by_dld_phone

    get_settings.cache_clear()
    req = parse_lookup_input(args.phone)
    from scrapers.errors import ExtractionError

    try:
        payload = await resolve_owner_by_dld_phone(req.external_id)
    except ExtractionError as exc:
        print(json.dumps({"phone": req.external_id, "complete": False, "error": exc.code, "detail": str(exc)}))
        return 2
    out = payload.model_dump()
    print(json.dumps({k: out[k] for k in ("owner_name", "owner_phone", "permit_number", "building") if out.get(k)}, indent=2))

    async with session_scope() as session:
        repo = ListingRepository(session, cache_ttl_days=get_settings().cache_ttl_days)
        listing = await repo.upsert_from_payload(payload.to_upsert(req))
        related = await repo.listings_by_owner_phone(req.external_id)
        if related:
            print("related_listings", [row.id for row in related])
        print("stored_listing_id", listing.id)

    return 0 if payload.owner_name and payload.owner_phone else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))