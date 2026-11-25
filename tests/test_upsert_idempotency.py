import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.repository import ListingRepository
from db.schemas import ListingUpsertPayload


@pytest.mark.asyncio
async def test_upsert_same_source_listing_id_updates_not_duplicates(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=30)
    base = ListingUpsertPayload(
        source="propertyfinder",
        source_listing_id="idem-100",
        building="Tower One",
        owner_name="Owner A",
        owner_phone="+971500000001",
        raw_payload={"v": 1},
    )
    first = await repo.upsert_from_payload(base)
    second = await repo.upsert_from_payload(
        ListingUpsertPayload(
            source="propertyfinder",
            source_listing_id="idem-100",
            building="Tower One Updated",
            owner_name="Owner B",
            owner_phone="+971500000002",
            raw_payload={"v": 2},
        )
    )
    await db_session.commit()

    found = await repo.get_by_source_id("propertyfinder", "idem-100")
    assert found is not None
    assert first.id == second.id == found.id
    assert found.building == "Tower One Updated"
    assert found.owner_name == "Owner B"
    assert found.raw_payload == {"v": 2}


@pytest.mark.asyncio
async def test_upsert_same_permit_merges_record(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=30)
    await repo.upsert_from_payload(
        ListingUpsertPayload(
            source="trakheesi",
            permit_number="7123456789012",
            permit_status="valid",
            raw_payload={},
        )
    )
    updated = await repo.upsert_from_payload(
        ListingUpsertPayload(
            source="trakheesi",
            permit_number="7123456789012",
            permit_status="expired",
            owner_phone="+971509999999",
            raw_payload={"refresh": True},
        )
    )
    await db_session.commit()

    found = await repo.get_by_permit("7123456789012")
    assert found is not None
    assert found.id == updated.id
    assert found.permit_status == "expired"
    assert found.owner_phone == "+971509999999"