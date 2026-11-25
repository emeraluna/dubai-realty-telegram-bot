"""Pull Madmoun integration JSON (file or live API), update DB, run DLD owner + resolve."""
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

LISTING_ID = 1
PF_URL = (
    "https://www.propertyfinder.ae/en/plp/buy/apartment-for-sale-dubai-jumeirah-village-circle"
    "-district-17-binghatti-grove-168788844.html"
)
GUID = "qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme"
VALIDATION = (
    "https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation"
    f"?khevJujtDig={GUID}"
)
DEFAULT_JSON = ROOT / "data" / "madmoun_168788844.json"


def _load_env() -> None:
    db_file = ROOT / "data" / "realty.db"
    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{db_file.as_posix()}")
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "DATABASE_URL" and not db_file.is_file():
            os.environ.setdefault(key.strip(), value.strip())
        elif key.strip() != "DATABASE_URL":
            os.environ.setdefault(key.strip(), value.strip())


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--live", action="store_true", help="POST integration API (needs CAPTCHA_API_KEY)")
    parser.add_argument("--no-resolve", action="store_true", help="Skip 5h resolve loop")
    args = parser.parse_args()

    _load_env()
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(ROOT / 'data' / 'realty.db').as_posix()}"
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "t")
    os.environ.setdefault("APIFY_TOKEN", "a")
    os.environ.setdefault("SCRAPEFORGE_KEY", "s")
    os.environ.setdefault("MADMOUN_PLAYWRIGHT_ENABLED", "false")
    dld_db = ROOT / "data" / "dld_owners.sqlite"
    if dld_db.exists():
        os.environ.setdefault("DLD_OWNER_DATABASE_URL", f"sqlite+aiosqlite:///{dld_db.as_posix()}")

    from config.settings import get_settings
    from db.repository import ListingRepository
    from db.schemas import ListingUpsertPayload
    from db.session import session_scope
    from scrapers.payload import ListingPayload, merge_payloads
    from scrapers.trakheesi_integration import (
        integration_to_listing_payload,
        post_madmoun_integration,
    )
    from services.dld_owner_lookup import enrich_owner_from_dld_sources
    from services.owner_broker_guard import strip_broker_owner
    from services.owner_resolve_pipeline import resolve_owner_for_listing

    get_settings.cache_clear()

    if args.live:
        data = await post_madmoun_integration(GUID, page_url=VALIDATION)
        args.json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    elif not args.json.is_file():
        print("missing json", args.json)
        return 1
    else:
        data = json.loads(args.json.read_text(encoding="utf-8"))

    patch = integration_to_listing_payload(GUID, data, url=VALIDATION)

    async with session_scope() as session:
        repo = ListingRepository(session, cache_ttl_days=get_settings().cache_ttl_days)
        listing = await repo.get_by_id(LISTING_ID)
        if listing is None:
            print("listing missing", LISTING_ID)
            return 1

        base = ListingPayload(
            source=listing.source,
            source_url=listing.source_url,
            source_listing_id=listing.source_listing_id,
            unit_number=listing.unit_number,
            floor=listing.floor,
            building=listing.building,
            community=listing.community,
            developer=listing.developer,
            size_sqft=listing.size_sqft,
            plot_number=listing.plot_number,
            permit_number=listing.permit_number,
            permit_status=listing.permit_status,
            owner_name=listing.owner_name,
            owner_phone=listing.owner_phone,
            raw_payload=dict(listing.raw_payload or {}),
        )
        merged = merge_payloads(base, patch)
        for field in ("owner_name", "owner_phone"):
            val = getattr(merged, field)
            if isinstance(val, str) and val.strip().upper().startswith("REPLACE_WITH"):
                merged = merged.model_copy(update={field: None})
        if not patch.owner_name and not patch.owner_phone:
            merged = merged.model_copy(update={"owner_name": None, "owner_phone": None})

        upsert = ListingUpsertPayload(
            source=listing.source,
            source_url=listing.source_url,
            source_listing_id=listing.source_listing_id,
            unit_number=merged.unit_number,
            floor=merged.floor,
            building=merged.building or listing.building,
            community=merged.community,
            developer=merged.developer,
            size_sqft=merged.size_sqft,
            plot_number=merged.plot_number,
            permit_number=merged.permit_number or listing.permit_number,
            permit_status=merged.permit_status,
            owner_name=merged.owner_name,
            owner_phone=merged.owner_phone,
            raw_payload=merged.raw_payload or {},
        )
        await repo.upsert_from_payload(upsert)

        listing = await repo.get_by_id(LISTING_ID)
        assert listing is not None
        merged2 = strip_broker_owner(await enrich_owner_from_dld_sources(listing, merged))
        if merged2.owner_name or merged2.owner_phone:
            await repo.upsert_from_payload(
                ListingUpsertPayload(
                    source=listing.source,
                    source_url=listing.source_url,
                    source_listing_id=listing.source_listing_id,
                    owner_name=merged2.owner_name,
                    owner_phone=merged2.owner_phone,
                    raw_payload=merged2.raw_payload or {},
                )
            )

    async with session_scope() as session:
        repo = ListingRepository(session, cache_ttl_days=get_settings().cache_ttl_days)
        listing = await repo.get_by_id(LISTING_ID)
    if listing is None:
        return 1

    broker = (listing.raw_payload or {}).get("trakheesi_integration", {}).get("broker")
    print(
        "owner",
        listing.owner_name,
        listing.owner_phone,
        "permit",
        listing.permit_number,
        "building",
        listing.building,
    )
    if broker:
        print("broker", json.dumps(broker, ensure_ascii=False))

    has_owner = bool(
        listing.owner_name
        and listing.owner_phone
        and not str(listing.owner_name).startswith("REPLACE_")
    )
    if args.no_resolve:
        return 0 if has_owner else 2

    async with session_scope() as session:
        repo = ListingRepository(session, cache_ttl_days=get_settings().cache_ttl_days)
        outcome = await resolve_owner_for_listing(
            repo,
            listing_id=LISTING_ID,
            requested_input=PF_URL,
        )
    print("resolve", outcome.success, outcome.message)
    return 0 if outcome.success and outcome.listing and outcome.listing.owner_name else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))