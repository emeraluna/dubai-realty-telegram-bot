from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from scrapers.actor_maps import ApifyListingRecord
from scrapers.payload import ListingPayload
from services.owner_enrichment import enrich_owner_from_dld, permit_eligible_for_dld


def test_apify_does_not_map_agent_phone_to_owner() -> None:
    record = ApifyListingRecord.model_validate(
        {
            "listingId": "1",
            "agentName": "Listing Agent",
            "agentPhone": "+971501046096",
            "mobile": "+971501046096",
        }
    )
    payload = record.to_listing_payload(source="propertyfinder")
    assert payload.owner_name is None
    assert payload.owner_phone is None


def test_permit_eligible_for_dld() -> None:
    assert permit_eligible_for_dld("7123456789012")
    assert not permit_eligible_for_dld("1106530")


@pytest.mark.asyncio
async def test_enrich_owner_from_dld_merges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("DLD_OWNER_ENRICHMENT", "true")
    from config.settings import get_settings

    get_settings.cache_clear()

    listing = ListingPayload(
        source="propertyfinder",
        building="Tower",
        permit_number="7123456789012",
    )
    dld = ListingPayload(
        source="trakheesi",
        owner_name="DLD Owner",
        owner_phone="+971504445566",
        permit_number="7123456789012",
    )

    with patch("services.owner_enrichment.fetch_dld_permit_by_digits", AsyncMock(return_value=dld)):
        merged = await enrich_owner_from_dld(listing)

    assert merged.owner_name == "DLD Owner"
    assert merged.owner_phone == "+971504445566"
    assert merged.building == "Tower"