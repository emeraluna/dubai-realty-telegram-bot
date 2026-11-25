from scrapers.actor_maps import ApifyListingRecord, DldPermitRecord, ScrapeForgeListingRecord


def test_apify_owner_field_aliases() -> None:
    record = ApifyListingRecord.model_validate(
        {
            "listingId": "42",
            "url": "https://example",
            "buildingName": "B",
            "ownerName": "Owner PF",
            "ownerPhone": "+971500000111",
        }
    )
    payload = record.to_listing_payload(source="propertyfinder")
    assert payload.source_listing_id == "42"
    assert payload.owner_name == "Owner PF"
    assert payload.owner_phone == "+971500000111"


def test_scrapeforge_owner_field_aliases() -> None:
    record = ScrapeForgeListingRecord.model_validate(
        {
            "listing_id": "77",
            "building_name": "C",
            "owner_contact_name": "Owner SF",
            "owner_contact_phone": "+971500000222",
        }
    )
    payload = record.to_listing_payload(source="bayut")
    assert payload.owner_name == "Owner SF"
    assert payload.owner_phone == "+971500000222"


def test_dld_owner_field_aliases() -> None:
    record = DldPermitRecord.model_validate(
        {
            "permitNumber": "7123456789",
            "status": "valid",
            "ownerName": "Owner DLD",
            "mobileNumber": "+971500000333",
        }
    )
    payload = record.to_listing_payload()
    assert payload.permit_number == "7123456789"
    assert payload.owner_name == "Owner DLD"
    assert payload.owner_phone == "+971500000333"