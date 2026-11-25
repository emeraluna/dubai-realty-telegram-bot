from __future__ import annotations

from typing import Any

from db.models import Listing
from db.repository import ListingRepository


async def match_listing(repo: ListingRepository, fields: dict[str, Any]) -> Listing | None:
    permit = fields.get("permit_number")
    if permit:
        found = await repo.get_by_permit(str(permit))
        if found:
            return found

    listing_id = fields.get("source_listing_id")
    if listing_id:
        for source in ("propertyfinder", "bayut", "manual", "trakheesi"):
            found = await repo.get_by_source_id(source, str(listing_id))
            if found:
                return found

    url = fields.get("source_url")
    if url:
        found = await repo.get_by_source_url(str(url))
        if found:
            return found

    unit = fields.get("unit_number")
    building = fields.get("building")
    if unit and building:
        found = await repo.get_by_unit_and_building(str(unit), str(building))
        if found:
            return found

    return None