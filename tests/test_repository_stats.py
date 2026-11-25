import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.repository import ListingRepository
from db.schemas import ListingUpsertPayload


@pytest.mark.asyncio
async def test_user_stats_and_export(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=30)
    listing = await repo.upsert_from_payload(
        ListingUpsertPayload(source="bayut", source_listing_id="exp-1", raw_payload={})
    )
    await repo.record_lookup(
        listing_id=listing.id,
        telegram_user_id=55,
        requested_input="url",
        cache_hit=True,
    )
    await repo.record_lookup(
        listing_id=listing.id,
        telegram_user_id=55,
        requested_input="url",
        cache_hit=False,
    )
    await db_session.commit()

    stats = await repo.user_stats(55)
    assert stats["lookups_total"] == 2
    assert stats["cache_hits"] == 1
    assert stats["listings_archived"] == 1

    rows = await repo.listings_for_user_export(55)
    assert len(rows) == 1
    assert rows[0].source_listing_id == "exp-1"