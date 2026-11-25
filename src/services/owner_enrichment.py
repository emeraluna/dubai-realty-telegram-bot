from __future__ import annotations

import re
import structlog

from config import get_settings
from scrapers.dld_permit import fetch_dld_permit_by_digits
from scrapers.errors import ExtractionError
from scrapers.madmoun_validation import fetch_madmoun_validation
from scrapers.payload import ListingPayload, merge_payloads
from services.permit_candidates import collect_permit_candidates, collect_validation_urls

log = structlog.get_logger(__name__)

_DIGITS = re.compile(r"\d+")


def permit_digits(permit_number: str | None) -> str | None:
    if not permit_number:
        return None
    joined = "".join(_DIGITS.findall(str(permit_number)))
    return joined or None


def permit_eligible_for_dld(permit_number: str | None) -> bool:
    digits = permit_digits(permit_number)
    if not digits:
        return False
    settings = get_settings()
    return settings.trakheesi_permit_min_length <= len(digits) <= settings.trakheesi_permit_max_length


def _dld_candidates(payload: ListingPayload) -> list[str]:
    settings = get_settings()
    seeds = collect_permit_candidates(payload.raw_payload)
    if payload.permit_number:
        seeds.insert(0, payload.permit_number)
    found: set[str] = set()
    for seed in seeds:
        digits = permit_digits(seed)
        if not digits:
            continue
        if settings.trakheesi_permit_min_length <= len(digits) <= settings.trakheesi_permit_max_length:
            found.add(digits)
        if settings.dld_try_ad_license:
            if settings.dld_ad_license_min_length <= len(digits) <= settings.dld_ad_license_max_length:
                found.add(digits)
    return sorted(found, key=lambda x: (-len(x), x))


async def enrich_owner_from_dld(payload: ListingPayload) -> ListingPayload:
    settings = get_settings()
    if not settings.dld_owner_enrichment:
        return payload

    if payload.owner_name and payload.owner_phone:
        return payload

    merged = payload
    for url in collect_validation_urls(payload.raw_payload):
        try:
            patch = await fetch_madmoun_validation(url)
            merged = merge_payloads(merged, patch)
            if merged.owner_name and merged.owner_phone:
                return merged
        except ExtractionError as exc:
            log.info("owner_enrichment.madmoun_skipped", code=exc.code, url=url)

    for digits in _dld_candidates(payload):
        try:
            patch = await fetch_dld_permit_by_digits(digits)
        except ExtractionError as exc:
            log.info("owner_enrichment.dld_skipped", permit=digits, code=exc.code)
            continue
        if not patch.owner_name and not patch.owner_phone:
            continue
        merged = merge_payloads(merged, patch)
        merged.raw_payload = {
            **(merged.raw_payload or {}),
            "owner_enrichment": {"permit": digits, "source": "dld"},
        }
        log.info(
            "owner_enrichment.dld_applied",
            permit=digits,
            has_name=bool(merged.owner_name),
            has_phone=bool(merged.owner_phone),
        )
        if merged.owner_name and merged.owner_phone:
            break

    return merged