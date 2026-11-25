from __future__ import annotations

import csv
import io
from typing import Iterable

from db.models import Listing

CSV_HEADERS = [
    "id",
    "source",
    "source_url",
    "source_listing_id",
    "unit_number",
    "floor",
    "building",
    "community",
    "developer",
    "size_sqft",
    "plot_number",
    "permit_number",
    "permit_status",
    "owner_name",
    "owner_phone",
    "first_seen_at",
    "last_seen_at",
    "lookup_count",
]


def listing_to_row(listing: Listing) -> list[str]:
    return [
        str(listing.id),
        listing.source or "",
        listing.source_url or "",
        listing.source_listing_id or "",
        listing.unit_number or "",
        listing.floor or "",
        listing.building or "",
        listing.community or "",
        listing.developer or "",
        str(listing.size_sqft) if listing.size_sqft is not None else "",
        listing.plot_number or "",
        listing.permit_number or "",
        listing.permit_status or "",
        listing.owner_name or "",
        listing.owner_phone or "",
        listing.first_seen_at.isoformat() if listing.first_seen_at else "",
        listing.last_seen_at.isoformat() if listing.last_seen_at else "",
        str(listing.lookup_count),
    ]


def listings_to_csv_bytes(listings: Iterable[Listing]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS)
    for listing in listings:
        writer.writerow(listing_to_row(listing))
    return buffer.getvalue().encode("utf-8-sig")