from __future__ import annotations

import structlog

from db.models import Listing
from scrapers.dld_owner_api import fetch_dld_owner_by_key
from scrapers.dld_private_owner import resolve_owner_via_dld_private
from scrapers.dld_private_owner import fetch_trakheesi_revamp_owner
from scrapers.trakheesi_integration import integration_to_listing_payload, post_madmoun_integration
from scrapers.errors import ExtractionError
from scrapers.madmoun_validation import fetch_madmoun_validation
from scrapers.payload import ListingPayload, merge_payloads
from scrapers.trakheesi_runtime import parse_listing_guid_from_validation_url
from scrapers.madmoun_cache import load_cached_integration_by_guid
from services.owner_broker_guard import strip_broker_owner
from services.dld_owner_database import fetch_owner_from_dld_database
from services.owner_registry_file import lookup_owner_file
from services.permit_candidates import (
    collect_listing_guids,
    collect_real_estate_numbers,
    collect_transaction_numbers,
    collect_validation_urls,
)

log = structlog.get_logger(__name__)


def _listing_lookup_fields(listing: Listing, merged: ListingPayload) -> dict[str, object]:
    guids = collect_listing_guids(listing.raw_payload, merged.raw_payload)
    txns = collect_transaction_numbers(listing.raw_payload, merged.raw_payload)
    guid = guids[0] if guids else None
    if not guid:
        for url in collect_validation_urls(listing.raw_payload, merged.raw_payload):
            guid = parse_listing_guid_from_validation_url(url)
            if guid:
                break
    estates = collect_real_estate_numbers(listing.raw_payload, merged.raw_payload)
    integration = (merged.raw_payload or {}).get("trakheesi_integration") or {}
    property_id = integration.get("api_response", {}).get("Response", {}).get("PropertyId")
    return {
        "permit_number": merged.permit_number or listing.permit_number,
        "transaction_number": txns[0] if txns else None,
        "listing_guid": guid,
        "real_estate_number": estates[0] if estates else None,
        "property_id": str(property_id) if property_id is not None else None,
        "unit_number": merged.unit_number or listing.unit_number,
        "building": merged.building or listing.building,
        "plot_number": merged.plot_number or listing.plot_number,
        "source_listing_id": listing.source_listing_id,
    }


async def enrich_owner_from_dld_sources(
    listing: Listing,
    merged: ListingPayload,
) -> ListingPayload:
    fields = _listing_lookup_fields(listing, merged)

    guid = fields.get("listing_guid")
    if isinstance(guid, str) and guid:
        cached = load_cached_integration_by_guid(guid)
        if cached:
            url = next(iter(collect_validation_urls(listing.raw_payload, merged.raw_payload)), None)
            patch = integration_to_listing_payload(guid, cached, url=url)
            merged = strip_broker_owner(merge_payloads(merged, patch))
            fields = _listing_lookup_fields(listing, merged)

    seed_phone = listing.owner_phone or merged.owner_phone
    if seed_phone:
        try:
            from services.owner_phone_lookup import resolve_owner_by_dld_phone

            patch = await resolve_owner_by_dld_phone(str(seed_phone))
            merged = strip_broker_owner(merge_payloads(merged, patch))
            if merged.owner_name and merged.owner_phone:
                log.info("dld_phone_enrich.hit", listing_id=listing.id)
                return merged
        except ExtractionError as exc:
            log.info("dld_phone_enrich.miss", code=exc.code, listing_id=listing.id)

    try:
        patch = lookup_owner_file(fields)
        merged = merge_payloads(merged, patch)
        if merged.owner_name and merged.owner_phone:
            log.info("owner_registry_file.hit", listing_id=listing.id)
            return merged
    except ExtractionError as exc:
        log.info("owner_registry_file.miss", code=exc.code, listing_id=listing.id)

    try:
        patch = await fetch_owner_from_dld_database(fields)
        merged = strip_broker_owner(merge_payloads(merged, patch))
        if merged.owner_name and merged.owner_phone:
            return merged
    except ExtractionError as exc:
        log.info("dld_owner_database.miss", code=exc.code, listing_id=listing.id)

    for url in collect_validation_urls(listing.raw_payload, merged.raw_payload):
        guid = fields.get("listing_guid")
        if isinstance(guid, str) and guid:
            try:
                data = await post_madmoun_integration(guid, page_url=url)
                patch = integration_to_listing_payload(guid, data, url=url)
                merged = merge_payloads(merged, patch)
                fields = _listing_lookup_fields(listing, merged)
            except ExtractionError as exc:
                log.info("dld_integration.miss", code=exc.code, listing_id=listing.id)

    guid_val = fields.get("listing_guid")
    if isinstance(guid_val, str) and guid_val:
        try:
            patch = await fetch_trakheesi_revamp_owner(guid_val)
            merged = strip_broker_owner(merge_payloads(merged, patch))
            if merged.owner_name and merged.owner_phone:
                log.info("trakheesi_revamp_owner.hit", listing_id=listing.id)
                return merged
        except ExtractionError as exc:
            log.info("trakheesi_revamp_owner.miss", code=exc.code, listing_id=listing.id)

    estates = collect_real_estate_numbers(listing.raw_payload, merged.raw_payload)
    for estate in estates:
        for key in (estate, fields.get("transaction_number"), fields.get("permit_number")):
            if not key or str(key).strip() in {"", "-1"}:
                continue
            try:
                patch = await fetch_dld_owner_by_key(str(key).strip())
                merged = strip_broker_owner(merge_payloads(merged, patch))
                if merged.owner_name and merged.owner_phone:
                    log.info("dld_owner_api.real_estate_hit", key=key, listing_id=listing.id)
                    return merged
            except ExtractionError as exc:
                log.info("dld_owner_api.real_estate_miss", key=key, code=exc.code)

    try:
        patch = await resolve_owner_via_dld_private(
            listing_guid=str(fields["listing_guid"]) if fields.get("listing_guid") else None,
            real_estate_number=str(fields["real_estate_number"])
            if fields.get("real_estate_number")
            else None,
            property_id=str(fields["property_id"]) if fields.get("property_id") else None,
            transaction_number=str(fields["transaction_number"])
            if fields.get("transaction_number")
            else None,
        )
        merged = merge_payloads(merged, patch)
        if merged.owner_name and merged.owner_phone:
            log.info("dld_private_owner.hit", listing_id=listing.id)
            return merged
    except ExtractionError as exc:
        log.info("dld_private_owner.miss", code=exc.code, listing_id=listing.id)

    keys: list[str] = []
    for name in ("transaction_number", "listing_guid", "permit_number", "source_listing_id"):
        val = fields.get(name)
        if val and str(val).strip():
            keys.append(str(val).strip())

    seen: set[str] = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        try:
            patch = await fetch_dld_owner_by_key(key)
            merged = merge_payloads(merged, patch)
            if merged.owner_name and merged.owner_phone:
                log.info("dld_owner_api.hit", key=key, listing_id=listing.id)
                return merged
        except ExtractionError as exc:
            log.info("dld_owner_api.miss", key=key, code=exc.code)

    for url in collect_validation_urls(listing.raw_payload, merged.raw_payload):
        try:
            patch = await fetch_madmoun_validation(url)
            merged = merge_payloads(merged, patch)
            fields = _listing_lookup_fields(listing, merged)
            patch = await fetch_owner_from_dld_database(fields)
            merged = merge_payloads(merged, patch)
            if merged.owner_name and merged.owner_phone:
                return merged
        except ExtractionError as exc:
            log.info("dld_owner_repass.miss", code=exc.code, listing_id=listing.id)

    return strip_broker_owner(merged)