from __future__ import annotations

import structlog

from scrapers.dld_phone_owner import fetch_dld_owner_by_phone
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload, merge_payloads
from services.dld_owner_database import fetch_owner_from_dld_database_by_phone
from services.owner_broker_guard import strip_broker_owner
from services.owner_registry_file import lookup_owner_by_phone
from services.uae_phone import canonical_uae_mobile

log = structlog.get_logger(__name__)


async def resolve_owner_by_dld_phone(phone: str) -> ListingPayload:
    canonical = canonical_uae_mobile(phone)
    if not canonical:
        raise ExtractionError(
            code="dld_phone_invalid",
            message="invalid UAE mobile",
            extractor="dld_phone",
            source="dld",
        )

    merged = ListingPayload(
        source="dld",
        source_listing_id=canonical,
        source_url=f"dld-phone:{canonical}",
        owner_phone=canonical,
    )

    try:
        patch = lookup_owner_by_phone(canonical)
        merged = strip_broker_owner(merge_payloads(merged, patch))
        if merged.owner_name and merged.owner_phone:
            log.info("owner_phone_lookup.hit", source="owner_registry_phone", phone=canonical)
            return merged
    except ExtractionError as exc:
        log.info("owner_phone_lookup.miss", source="owner_registry_phone", code=exc.code, phone=canonical)

    try:
        patch = await fetch_owner_from_dld_database_by_phone(canonical)
        merged = strip_broker_owner(merge_payloads(merged, patch))
        if merged.owner_name and merged.owner_phone:
            log.info("owner_phone_lookup.hit", source="dld_db_phone", phone=canonical)
            return merged
    except ExtractionError as exc:
        log.info("owner_phone_lookup.miss", source="dld_db_phone", code=exc.code, phone=canonical)

    try:
        patch = await fetch_dld_owner_by_phone(canonical)
        merged = strip_broker_owner(merge_payloads(merged, patch))
        if merged.owner_name and merged.owner_phone:
            log.info("owner_phone_lookup.hit", source="dld_api_phone", phone=canonical)
            return merged
        if merged.owner_name or merged.permit_number:
            log.info("owner_phone_lookup.partial", source="dld_api_phone", phone=canonical)
    except ExtractionError as exc:
        log.info("owner_phone_lookup.miss", source="dld_api_phone", code=exc.code, phone=canonical)

    if merged.owner_name or (merged.owner_phone and merged.owner_phone != canonical):
        return merged
    raise ExtractionError(
        code="dld_phone_no_owner",
        message="no owner record for phone",
        extractor="dld_phone",
        source="dld",
    )