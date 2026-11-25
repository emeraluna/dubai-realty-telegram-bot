from scrapers.payload import ListingPayload, merge_payloads
from scrapers.trakheesi_integration import integration_to_listing_payload
from services.owner_broker_guard import owner_matches_broker, strip_broker_owner
from services.owner_source_attempts import owner_complete


def test_integration_does_not_set_broker_as_owner() -> None:
    data = {
        "Code": 0,
        "Response": {
            "LicenseNumber": "1106530",
            "PermitNumber": "153343",
            "CardHolderNameEn": "Broker Person",
            "CardHolderMobile": "971501046096",
            "BuildingNameEn": "Binghatti Grove",
        },
        "Errors": [],
    }
    payload = integration_to_listing_payload("guid", data, url="http://example/validation")
    assert payload.owner_name is None
    assert payload.owner_phone is None
    assert payload.raw_payload["trakheesi_integration"]["broker"]["broker_name_en"] == "Broker Person"


def test_strip_broker_owner_clears_stale_contact() -> None:
    cached = integration_to_listing_payload(
        "guid",
        {
            "Response": {
                "LicenseNumber": "1106530",
                "CardHolderNameEn": "Broker Person",
                "CardHolderMobile": "971501046096",
            }
        },
        url=None,
    )
    stale = ListingPayload(
        source="propertyfinder",
        owner_name="Broker Person",
        owner_phone="971501046096",
        raw_payload={},
    )
    merged = merge_payloads(stale, cached)
    merged = strip_broker_owner(merged)
    assert not owner_complete(merged)
    assert owner_matches_broker("Broker Person", "971501046096", raw_payload=merged.raw_payload)