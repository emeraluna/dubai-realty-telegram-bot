from datetime import UTC, datetime

from bot.formatters import format_listing_html
from db.models import Listing


def test_format_owner_missing_message() -> None:
    listing = Listing(
        source="bayut",
        building="B",
        community="C",
        developer="D",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        lookup_count=0,
        raw_payload={},
    )
    text = format_listing_html(listing, cache_hit=True)
    assert "owner contact not available from source" in text
    assert "cached" in text


def test_format_includes_owner_fields() -> None:
    listing = Listing(
        source="propertyfinder",
        building="B",
        owner_name="Owner",
        owner_phone="+971500000000",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        lookup_count=1,
        raw_payload={},
    )
    text = format_listing_html(listing, cache_hit=False)
    assert "Owner" in text
    assert "+971500000000" in text
    assert "fresh extraction" in text