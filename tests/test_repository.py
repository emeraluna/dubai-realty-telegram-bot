from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.repository import ListingRepository
from db.schemas import ListingUpsertPayload


@pytest.mark.asyncio
async def test_upsert_and_get_by_source_id(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=30)
    payload = ListingUpsertPayload(
        source="propertyfinder",
        source_url="https://example.com/pf/1",
        source_listing_id="pf-1",
        building="Tower A",
        raw_payload={"k": "v"},
    )
    created = await repo.upsert_from_payload(payload)
    await db_session.commit()

    found = await repo.get_by_source_id("propertyfinder", "pf-1")
    assert found is not None
    assert found.id == created.id
    assert found.building == "Tower A"


@pytest.mark.asyncio
async def test_get_by_permit(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=30)
    payload = ListingUpsertPayload(
        source="bayut",
        permit_number="PERMIT-99",
        owner_phone="+971500000000",
        raw_payload={},
    )
    await repo.upsert_from_payload(payload)
    await db_session.commit()

    found = await repo.get_by_permit("PERMIT-99")
    assert found is not None
    assert found.owner_phone == "+971500000000"


@pytest.mark.asyncio
async def test_record_lookup(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=30)
    listing = await repo.upsert_from_payload(
        ListingUpsertPayload(source="bayut", source_listing_id="b-1", raw_payload={})
    )
    lookup = await repo.record_lookup(
        listing_id=listing.id,
        telegram_user_id=42,
        requested_input="https://bayut.com/x",
        cache_hit=False,
    )
    await db_session.commit()
    assert lookup.listing_id == listing.id
    assert lookup.cache_hit is False


@pytest.mark.asyncio
async def test_cache_fresh_and_bump(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=7)
    listing = await repo.upsert_from_payload(
        ListingUpsertPayload(source="propertyfinder", source_listing_id="pf-2", raw_payload={})
    )
    listing.last_seen_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.flush()

    assert repo.is_cache_fresh(listing) is True
    updated = await repo.bump_cache_hit(listing)
    assert updated.lookup_count == 1