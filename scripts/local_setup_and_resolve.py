from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DATA = ROOT / "data"
DB_FILE = DATA / "realty.db"


def write_env() -> None:
    env_path = ROOT / ".env"
    DATA.mkdir(parents=True, exist_ok=True)
    db_url = os.getenv("LOCAL_RESOLVE_DATABASE_URL")
    if not db_url:
        db_url = f"sqlite+aiosqlite:///{DB_FILE.as_posix()}"
    lines = [
        f"TELEGRAM_BOT_TOKEN={os.getenv('TELEGRAM_BOT_TOKEN', 'local-dev-token')}",
        f"APIFY_TOKEN={os.getenv('APIFY_TOKEN', '')}",
        f"SCRAPEFORGE_KEY={os.getenv('SCRAPEFORGE_KEY', '')}",
        f"DATABASE_URL={db_url}",
        f"APIFY_ACTOR_PROPERTYFINDER={os.getenv('APIFY_ACTOR_PROPERTYFINDER', '')}",
        f"APIFY_ACTOR_BAYUT={os.getenv('APIFY_ACTOR_BAYUT', '')}",
        f"SCRAPEFORGE_BASE_URL={os.getenv('SCRAPEFORGE_BASE_URL', '')}",
        "LOG_LEVEL=INFO",
        "DLD_OWNER_ENRICHMENT=true",
        "DLD_TRY_AD_LICENSE=true",
        "DLD_AD_LICENSE_MIN_LENGTH=5",
        "DLD_AD_LICENSE_MAX_LENGTH=15",
        "OWNER_RESOLVE_ENABLED=true",
        f"OWNER_RESOLVE_TIMEOUT_HOURS={os.getenv('OWNER_RESOLVE_TIMEOUT_HOURS', '5')}",
        f"OWNER_RESOLVE_POLL_SECONDS={os.getenv('OWNER_RESOLVE_POLL_SECONDS', '300')}",
        "TRAKHEESI_PERMIT_MIN_LENGTH=10",
        "TRAKHEESI_PERMIT_MAX_LENGTH=15",
        "DLD_PERMIT_API_URL=https://b2c.dubailand.gov.ae/mv-portal-service/public/permit",
        "MADMOUN_PLAYWRIGHT_ENABLED=false",
        "DLD_OWNER_DATABASE_ENABLED=true",
        f"DLD_OWNER_DATABASE_URL={os.getenv('DLD_OWNER_DATABASE_URL', 'sqlite+aiosqlite:///' + (DATA / 'dld_owners.sqlite').as_posix())}",
        "EXTRACTOR_PRIORITY_PROPERTYFINDER=apify,scrapeforge,direct",
    ]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["DATABASE_URL"] = db_url


async def init_schema() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from config.settings import get_settings
    from db import models  # noqa: F401
    from db.base import Base

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def seed_listing(url: str) -> int:
    from datetime import UTC, datetime

    from config.settings import get_settings
    from db.enums import OwnerSource
    from db.models import Listing
    from db.session import session_scope

    get_settings.cache_clear()
    validation = (
        "https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation"
        "?khevJujtDig=qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme"
    )
    now = datetime.now(UTC)
    listing = Listing(
        source="propertyfinder",
        source_url=url,
        source_listing_id="168788844",
        building="Binghatti Grove",
        community="Jumeirah Village Circle",
        developer="Binghatti Developers FZE",
        unit_number=None,
        size_sqft=792.0,
        permit_number="1106530",
        permit_status=None,
        owner_name=None,
        owner_phone=None,
        owner_source=OwnerSource.UNKNOWN.value,
        raw_payload={
            "direct": {
                "rera": {
                    "issued_license_number": "1106530",
                    "permit_validation_url": validation,
                },
                "permit_validation_url": validation,
            },
            "seed": {"source": "local_setup_and_resolve"},
        },
        first_seen_at=now,
        last_seen_at=now,
        lookup_count=0,
    )
    async with session_scope() as session:
        from sqlalchemy import select

        existing = await session.scalar(
            select(Listing).where(
                Listing.source == listing.source,
                Listing.source_listing_id == listing.source_listing_id,
            )
        )
        if existing:
            existing.last_seen_at = now
            existing.raw_payload = listing.raw_payload
            if listing.permit_number:
                existing.permit_number = listing.permit_number
            await session.flush()
            return existing.id
        session.add(listing)
        await session.flush()
        return listing.id


async def run_resolve(listing_id: int, url: str) -> int:
    from config import configure_logging
    from config.settings import get_settings
    from db.repository import ListingRepository
    from db.session import session_scope
    from services.owner_resolve_pipeline import resolve_owner_for_listing

    settings = get_settings()
    configure_logging(settings.log_level)
    async with session_scope() as session:
        repo = ListingRepository(session, cache_ttl_days=settings.cache_ttl_days)
        outcome = await resolve_owner_for_listing(
            repo,
            listing_id=listing_id,
            requested_input=url,
        )
    print(
        f"success={outcome.success} attempts={outcome.attempts} message={outcome.message}",
        flush=True,
    )
    if outcome.listing:
        print(
            f"owner_name={outcome.listing.owner_name!r} owner_phone={outcome.listing.owner_phone!r}",
            flush=True,
        )
        print(f"permit={outcome.listing.permit_number!r} building={outcome.listing.building!r}", flush=True)
    return 0 if outcome.success else 2


def main() -> None:
    url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "https://www.propertyfinder.ae/en/plp/buy/apartment-for-sale-dubai-jumeirah-village-circle-district-17-binghatti-grove-168788844.html"
    )
    write_env()
    os.chdir(ROOT)
    asyncio.run(init_schema())
    listing_id = asyncio.run(seed_listing(url))
    code = asyncio.run(run_resolve(listing_id, url))
    raise SystemExit(code)


if __name__ == "__main__":
    main()