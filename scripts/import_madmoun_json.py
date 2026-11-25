"""Persist Trakheesi integration JSON into realty.db (broker + permit metadata; owner if present)."""
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

GUID = "qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme"
DEFAULT_URL = (
    "https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation"
    f"?khevJujtDig={GUID}"
)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file", type=Path, help="integration API JSON file")
    parser.add_argument("--listing-id", type=int, default=1)
    args = parser.parse_args()

    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "t")
    os.environ.setdefault("APIFY_TOKEN", "a")
    os.environ.setdefault("SCRAPEFORGE_KEY", "s")
    env_db = ROOT / ".env"
    if env_db.exists():
        for line in env_db.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip()

    data = json.loads(args.json_file.read_text(encoding="utf-8"))

    from config.settings import get_settings
    from db.repository import ListingRepository
    from db.session import session_scope
    from scrapers.trakheesi_integration import integration_to_listing_payload

    get_settings.cache_clear()
    patch = integration_to_listing_payload(GUID, data, url=DEFAULT_URL)

    async with session_scope() as session:
        repo = ListingRepository(session, cache_ttl_days=get_settings().cache_ttl_days)
        listing = await repo.get_by_id(args.listing_id)
        if listing is None:
            print("listing not found", args.listing_id)
            return 1
        updated = await repo.upsert_from_payload(listing.source, {**listing.__dict__, **patch.model_dump()})
        await session.commit()
        print(
            "updated listing",
            updated.id,
            "permit",
            updated.permit_number,
            "owner",
            updated.owner_name,
            updated.owner_phone,
        )
        broker = (patch.raw_payload or {}).get("trakheesi_integration", {}).get("broker")
        print("broker", json.dumps(broker, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))