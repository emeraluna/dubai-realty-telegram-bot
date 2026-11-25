from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.repository import ListingRepository
from db.schemas import ListingUpsertPayload
from services.listing_resolve import ListingResolveService


@pytest.mark.asyncio
async def test_resolve_cache_hit_skips_extract(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=30)
    listing = await repo.upsert_from_payload(
        ListingUpsertPayload(
            source="propertyfinder",
            source_listing_id="cache-1",
            building="Cached Tower",
            raw_payload={"cached": True},
        )
    )
    listing.last_seen_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.flush()

    calls = 0

    async def extract() -> ListingUpsertPayload:
        nonlocal calls
        calls += 1
        return ListingUpsertPayload(
            source="propertyfinder",
            source_listing_id="cache-1",
            building="Fresh Tower",
            raw_payload={"cached": False},
        )

    service = ListingResolveService(repo)
    result = await service.resolve_by_source_id(
        source="propertyfinder",
        source_listing_id="cache-1",
        telegram_user_id=100,
        requested_input="https://propertyfinder.ae/l/cache-1",
        extract=extract,
    )
    await db_session.commit()

    assert calls == 0
    assert result.cache_hit is True
    assert result.listing.building == "Cached Tower"
    assert result.listing.lookup_count == 1


@pytest.mark.asyncio
async def test_resolve_stale_calls_extract(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=7)
    listing = await repo.upsert_from_payload(
        ListingUpsertPayload(
            source="bayut",
            source_listing_id="stale-1",
            building="Old",
            raw_payload={},
        )
    )
    listing.last_seen_at = datetime.now(UTC) - timedelta(days=30)
    await db_session.flush()

    async def extract() -> ListingUpsertPayload:
        return ListingUpsertPayload(
            source="bayut",
            source_listing_id="stale-1",
            building="New",
            raw_payload={"refreshed": True},
        )

    service = ListingResolveService(repo)
    result = await service.resolve_by_source_id(
        source="bayut",
        source_listing_id="stale-1",
        telegram_user_id=200,
        requested_input="url",
        extract=extract,
    )
    await db_session.commit()

    assert result.cache_hit is False
    assert result.listing.building == "New"


@pytest.mark.asyncio
async def test_resolve_by_permit_cache_hit(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=30)
    listing = await repo.upsert_from_payload(
        ListingUpsertPayload(
            source="dld",
            permit_number="71123456789",
            permit_status="valid",
            raw_payload={},
        )
    )
    listing.last_seen_at = datetime.now(UTC)
    await db_session.flush()

    calls = 0

    async def extract() -> ListingUpsertPayload:
        nonlocal calls
        calls += 1
        return ListingUpsertPayload(
            source="dld",
            permit_number="71123456789",
            permit_status="changed",
            raw_payload={},
        )

    service = ListingResolveService(repo)
    result = await service.resolve_by_permit(
        permit_number="71123456789",
        telegram_user_id=300,
        requested_input="71123456789",
        extract=extract,
    )
    await db_session.commit()

    assert calls == 0
    assert result.cache_hit is True
    assert result.listing.permit_status == "valid"
    assert result.listing.lookup_count == 1