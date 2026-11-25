from __future__ import annotations

import html

from db.models import Listing


def _val(value: object | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"
    text = str(value).strip()
    return html.escape(text) if text else "—"


def format_listing_html(listing: Listing, *, cache_hit: bool) -> str:
    owner_name = listing.owner_name
    owner_phone = listing.owner_phone
    if owner_name and owner_phone:
        owner_block = (
            f"<b>Owner name:</b> {_val(owner_name)}\n"
            f"<b>Owner phone:</b> {_val(owner_phone)}"
        )
    elif owner_name or owner_phone:
        owner_block = (
            f"<b>Owner name:</b> {_val(owner_name)}\n"
            f"<b>Owner phone:</b> {_val(owner_phone)}"
        )
    else:
        owner_block = "owner contact not available from source"

    cache_line = "cached" if cache_hit else "fresh extraction"
    return (
        f"<b>Source:</b> {_val(listing.source)}\n"
        f"<b>Building:</b> {_val(listing.building)}\n"
        f"<b>Community:</b> {_val(listing.community)}\n"
        f"<b>Developer:</b> {_val(listing.developer)}\n"
        f"<b>Unit:</b> {_val(listing.unit_number)}\n"
        f"<b>Floor:</b> {_val(listing.floor)}\n"
        f"<b>Size (sqft):</b> {_val(listing.size_sqft)}\n"
        f"<b>Plot:</b> {_val(listing.plot_number)}\n"
        f"<b>Permit:</b> {_val(listing.permit_number)}\n"
        f"<b>Permit status:</b> {_val(listing.permit_status)}\n"
        f"{owner_block}\n"
        f"\n<i>{cache_line}</i>"
    )