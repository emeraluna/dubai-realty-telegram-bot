from __future__ import annotations

import structlog

from config import get_settings
from db.enums import OwnerSource
from db.models import Listing
from db.repository import ListingRepository
from scrapers.errors import ExtractionError
from scrapers.dld_permit import fetch_dld_permit_by_digits
from scrapers.madmoun_validation import fetch_madmoun_validation
from scrapers.payload import ListingPayload, merge_payloads
from services.dld_owner_lookup import enrich_owner_from_dld_sources
from services.owner_broker_guard import strip_broker_owner
from services.owner_enrichment import permit_digits
from services.input_parser import parse_lookup_input
from services.permit_candidates import collect_permit_candidates, collect_validation_urls

log = structlog.get_logger(__name__)


def _digit_permit_candidates(listing: Listing) -> list[str]:
    raw_permits = collect_permit_candidates(listing.raw_payload)
    seeds = [listing.permit_number, *raw_permits]
    out: set[str] = set()
    settings = get_settings()
    for seed in seeds:
        digits = permit_digits(seed)
        if not digits:
            continue
        if settings.trakheesi_permit_min_length <= len(digits) <= settings.trakheesi_permit_max_length:
            out.add(digits)
        if settings.dld_try_ad_license:
            if settings.dld_ad_license_min_length <= len(digits) <= settings.dld_ad_license_max_length:
                out.add(digits)
    return sorted(out, key=lambda x: (-len(x), x))


def _validation_urls(listing: Listing) -> list[str]:
    urls = collect_validation_urls(listing.raw_payload)
    return [u for u in urls if u.startswith("http")]


def owner_complete(payload: ListingPayload) -> bool:
    return bool(
        payload.owner_name
        and str(payload.owner_name).strip()
        and payload.owner_phone
        and str(payload.owner_phone).strip()
    )


async def attempt_manual_listing_match(repo: ListingRepository, listing: Listing) -> Listing | None:
    if listing.permit_number:
        row = await repo.get_by_permit(listing.permit_number)
        if row and row.owner_source == OwnerSource.MANUAL.value and (row.owner_name or row.owner_phone):
            return row
    if listing.unit_number and listing.building:
        row = await repo.get_by_unit_and_building(listing.unit_number, listing.building)
        if row and row.owner_source == OwnerSource.MANUAL.value and (row.owner_name or row.owner_phone):
            return row
    return None


async def run_owner_source_cycle(repo: ListingRepository, listing: Listing) -> ListingPayload | None:
    manual = await attempt_manual_listing_match(repo, listing)
    if manual:
        return ListingPayload(
            source=listing.source,
            source_url=listing.source_url,
            source_listing_id=listing.source_listing_id,
            unit_number=listing.unit_number,
            floor=listing.floor,
            building=listing.building or manual.building,
            community=listing.community or manual.community,
            developer=listing.developer,
            size_sqft=listing.size_sqft,
            plot_number=listing.plot_number,
            permit_number=listing.permit_number or manual.permit_number,
            permit_status=listing.permit_status,
            owner_name=manual.owner_name,
            owner_phone=manual.owner_phone,
            raw_payload={"owner_resolve": {"source": "manual_db", "listing_id": manual.id}},
        )

    keep_owner = listing.owner_source == OwnerSource.MANUAL.value
    base = ListingPayload(
        source=listing.source,
        source_url=listing.source_url,
        source_listing_id=listing.source_listing_id,
        unit_number=listing.unit_number,
        floor=listing.floor,
        building=listing.building,
        community=listing.community,
        developer=listing.developer,
        size_sqft=listing.size_sqft,
        plot_number=listing.plot_number,
        permit_number=listing.permit_number,
        permit_status=listing.permit_status,
        owner_name=listing.owner_name if keep_owner else None,
        owner_phone=listing.owner_phone if keep_owner else None,
        raw_payload=dict(listing.raw_payload or {}),
    )

    merged: ListingPayload = strip_broker_owner(base)

    for url in _validation_urls(listing):
        try:
            patch = await fetch_madmoun_validation(url)
            merged = strip_broker_owner(merge_payloads(merged, patch))
        except ExtractionError as exc:
            log.info("owner_source_cycle.madmoun_failed", url=url, code=exc.code)

    for digits in _digit_permit_candidates(listing):
        try:
            patch = await fetch_dld_permit_by_digits(digits)
            merged = strip_broker_owner(merge_payloads(merged, patch))
            if merged.owner_name or merged.owner_phone:
                log.info("owner_source_cycle.dld_hit", permit=digits, listing_id=listing.id)
        except ExtractionError as exc:
            log.info("owner_source_cycle.dld_failed", permit=digits, code=exc.code)

    merged = strip_broker_owner(await enrich_owner_from_dld_sources(listing, merged))

    if listing.source_url and listing.source == "propertyfinder" and not owner_complete(merged):
        pf_req = parse_lookup_input(listing.source_url)
        try:
            from scrapers.propertyfinder_api import fetch_propertyfinder_listing

            patch = await fetch_propertyfinder_listing(pf_req)
            merged = strip_broker_owner(merge_payloads(merged, patch))
        except ExtractionError as exc:
            log.info("owner_source_cycle.pf_api_failed", code=exc.code, listing_id=listing.id)
        if not owner_complete(merged):
            try:
                from scrapers.direct import DirectParserExtractor

                patch = await DirectParserExtractor().fetch(pf_req)
                merged = strip_broker_owner(merge_payloads(merged, patch))
            except ExtractionError as exc:
                log.info("owner_source_cycle.pf_direct_failed", code=exc.code, listing_id=listing.id)

    if owner_complete(merged):
        log.info("owner_source_cycle.owner_resolved", listing_id=listing.id)
        return merged

    if merged.owner_name or merged.owner_phone:
        merged = strip_broker_owner(merged)
        if owner_complete(merged):
            return merged

    if merged.raw_payload != (listing.raw_payload or {}) or merged.permit_number or merged.building:
        return merged.model_copy(update={"owner_name": None, "owner_phone": None})
    return None