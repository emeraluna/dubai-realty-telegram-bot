import pytest
import structlog.testing
from sqlalchemy.ext.asyncio import AsyncSession

from db.enums import OwnerSource
from db.repository import ListingRepository
from db.schemas import ListingUpsertPayload


@pytest.mark.asyncio
async def test_manual_owner_survives_scraped_upsert(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=30)
    listing, _ = await repo.upsert_manual_owner(
        None,
        {
            "permit_number": "7123999999999",
            "owner_name": "Manual Owner",
            "owner_phone": "+971500000111",
        },
        batch_id=1,
    )
    await db_session.flush()

    with structlog.testing.capture_logs() as captured:
        await repo.upsert_from_payload(
            ListingUpsertPayload(
                source="bayut",
                permit_number="7123999999999",
                source_listing_id="manual-match",
                owner_name="Scraped Owner",
                owner_phone="+971500000999",
                raw_payload={},
            )
        )

    await db_session.refresh(listing)
    assert listing.owner_name == "Manual Owner"
    assert listing.owner_phone == "+971500000111"
    assert listing.owner_source == OwnerSource.MANUAL.value
    assert any(e.get("event") == "owner_override_suppressed" for e in captured)


@pytest.mark.asyncio
async def test_scraped_fills_null_manual_owner_phone(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=30)
    listing, _ = await repo.upsert_manual_owner(
        None,
        {"permit_number": "7123888888888", "owner_name": "Name Only"},
        batch_id=2,
    )
    await db_session.flush()

    await repo.upsert_from_payload(
        ListingUpsertPayload(
            source="propertyfinder",
            permit_number="7123888888888",
            owner_phone="+971500000222",
            raw_payload={},
        )
    )
    await db_session.refresh(listing)
    assert listing.owner_name == "Name Only"
    assert listing.owner_phone == "+971500000222"
    assert listing.owner_source == OwnerSource.MANUAL.value


@pytest.mark.asyncio
async def test_scraped_owner_cleared_on_explicit_null_upsert(db_session: AsyncSession) -> None:
    repo = ListingRepository(db_session, cache_ttl_days=30)
    await repo.upsert_from_payload(
        ListingUpsertPayload(
            source="propertyfinder",
            source_listing_id="pf-clear-owner",
            owner_name="Wrong Broker",
            owner_phone="+971501046096",
            raw_payload={},
        )
    )
    listing = await repo.get_by_source_id("propertyfinder", "pf-clear-owner")
    assert listing is not None
    assert listing.owner_source == OwnerSource.SCRAPED.value

    await repo.upsert_from_payload(
        ListingUpsertPayload(
            source="propertyfinder",
            source_listing_id="pf-clear-owner",
            owner_name=None,
            owner_phone=None,
            raw_payload={"trakheesi_integration": {"broker": {"broker_phone": "+971501046096"}}},
        )
    )
    await db_session.refresh(listing)
    assert listing.owner_name is None
    assert listing.owner_phone is None
    assert listing.owner_source == OwnerSource.UNKNOWN.value