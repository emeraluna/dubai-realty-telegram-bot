from scrapers.payload import ListingPayload, merge_payloads


def test_merge_fills_missing_fields() -> None:
    base = ListingPayload(source="bayut", building="Tower A", owner_name=None)
    patch = ListingPayload(source="bayut", owner_name="Owner One", owner_phone="+971500000000")
    merged = merge_payloads(base, patch)
    assert merged.building == "Tower A"
    assert merged.owner_name == "Owner One"
    assert merged.owner_phone == "+971500000000"


def test_merge_owner_phone_prefers_longer_value() -> None:
    base = ListingPayload(owner_phone="+9715")
    patch = ListingPayload(owner_phone="+971500000001")
    merged = merge_payloads(base, patch)
    assert merged.owner_phone == "+971500000001"