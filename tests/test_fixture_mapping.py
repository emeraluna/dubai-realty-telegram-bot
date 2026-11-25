from __future__ import annotations

import json
from pathlib import Path

import pytest

from scrapers.actor_maps import ApifyListingRecord, DldPermitRecord, ScrapeForgeListingRecord
FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_apify_propertyfinder_fixture_mapping() -> None:
    raw = _load("apify_propertyfinder.json")
    record = ApifyListingRecord.model_validate(raw)
    payload = record.to_listing_payload(source="propertyfinder")
    assert payload.source_listing_id == "12345678"
    assert payload.building == "Marina Gate 1"
    assert payload.owner_name == "Khalid Owner"
    assert payload.owner_phone == "+971501112233"
    assert payload.permit_number == "711234567890"


def test_apify_bayut_fixture_mapping() -> None:
    raw = _load("apify_bayut.json")
    record = ApifyListingRecord.model_validate(raw)
    payload = record.to_listing_payload(source="bayut")
    assert payload.source_listing_id == "9876543"
    assert payload.community == "Business Bay"
    assert payload.owner_name == "Fatima Al M"
    assert payload.owner_phone == "+971502223344"
    assert payload.size_sqft == 2100.0


def test_scrapeforge_bayut_fixture_mapping() -> None:
    raw = _load("scrapeforge_bayut.json")
    record = ScrapeForgeListingRecord.model_validate(raw)
    payload = record.to_listing_payload(source="bayut")
    assert payload.source_listing_id == "5551212"
    assert payload.building == "Creek Rise"
    assert payload.owner_name == "Omar Seller"
    assert payload.owner_phone == "+971503334455"


def test_dld_trakheesi_fixture_mapping() -> None:
    wrapper = _load("dld_trakheesi.json")
    data = wrapper["data"]
    record = DldPermitRecord.model_validate(data)
    payload = record.to_listing_payload()
    assert payload.permit_number == "7123456789012"
    assert payload.permit_status == "Valid"
    assert payload.owner_name == "DLD Registered Owner"
    assert payload.owner_phone == "+971504445566"


@pytest.mark.parametrize(
    "fixture_name,source,expected_owner_phone",
    [
        ("apify_propertyfinder.json", "propertyfinder", "+971501112233"),
        ("apify_bayut.json", "bayut", "+971502223344"),
        ("scrapeforge_bayut.json", "bayut", "+971503334455"),
    ],
)
def test_owner_fields_present_in_fixture_maps(
    fixture_name: str,
    source: str,
    expected_owner_phone: str,
) -> None:
    raw = _load(fixture_name)
    if fixture_name.startswith("apify_"):
        payload = ApifyListingRecord.model_validate(raw).to_listing_payload(source=source)
    else:
        payload = ScrapeForgeListingRecord.model_validate(raw).to_listing_payload(source=source)
    assert payload.owner_name
    assert payload.owner_phone == expected_owner_phone


def test_trakheesi_fixture_unwrap_matches_extractor_normalization() -> None:
    wrapper = _load("dld_trakheesi.json")
    data = wrapper["data"]
    record = DldPermitRecord.model_validate(data)
    assert record.permit_number == "7123456789012"
    payload = record.to_listing_payload()
    assert payload.owner_phone == "+971504445566"