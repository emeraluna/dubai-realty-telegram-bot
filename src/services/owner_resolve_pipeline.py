from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog

from config import get_settings
from db.enums import OwnerSource
from db.models import Listing
from db.repository import ListingRepository
from db.schemas import ListingUpsertPayload
from scrapers.chain import ExtractorChain
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload, merge_payloads
from services.input_parser import parse_lookup_input
from services.lookup_request import LookupRequest
from services.owner_broker_guard import owner_matches_broker, strip_broker_owner
from services.owner_source_attempts import owner_complete, run_owner_source_cycle
from services.permit_candidates import collect_validation_urls

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class OwnerResolveOutcome:
    success: bool
    listing: Listing | None
    attempts: int
    message: str


def _deadline() -> datetime:
    settings = get_settings()
    return datetime.now(UTC) + timedelta(hours=settings.owner_resolve_timeout_hours)


async def _refresh_listing_payload(repo: ListingRepository, listing: Listing, requested_input: str) -> Listing:
    try:
        req = parse_lookup_input(requested_input)
    except Exception:
        if listing.source_url:
            req = LookupRequest(
                source=listing.source,  # type: ignore[arg-type]
                external_id=listing.source_listing_id or str(listing.id),
                raw_input=listing.source_url,
            )
        else:
            return listing

    if req.source == "trakheesi":
        return listing

    try:
        payload = await ExtractorChain().extract(req)
    except ExtractionError as exc:
        log.info("owner_resolve.refresh_skipped", listing_id=listing.id, code=exc.code)
        return listing

    upsert = await repo.upsert_from_payload(payload.to_upsert(req))
    return upsert


async def _persist_owner_patch(repo: ListingRepository, listing: Listing, patch: ListingPayload) -> Listing:
    merged = merge_payloads(
        ListingPayload(
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
            owner_name=listing.owner_name,
            owner_phone=listing.owner_phone,
            raw_payload=dict(listing.raw_payload or {}),
        ),
        patch,
    )
    req = LookupRequest(
        source=listing.source,  # type: ignore[arg-type]
        external_id=listing.source_listing_id or str(listing.id),
        raw_input=listing.source_url or "",
    )
    if listing.source == "trakheesi" and listing.permit_number:
        req = LookupRequest(source="trakheesi", external_id=listing.permit_number, raw_input=listing.permit_number)
    upsert = merged.to_upsert(req)
    merged = strip_broker_owner(merged)
    upsert_data = upsert.model_dump()
    upsert_data["owner_name"] = merged.owner_name
    upsert_data["owner_phone"] = merged.owner_phone
    return await repo.upsert_from_payload(ListingUpsertPayload(**upsert_data))


async def resolve_owner_for_listing(
    repo: ListingRepository,
    *,
    listing_id: int,
    requested_input: str,
    deadline: datetime | None = None,
) -> OwnerResolveOutcome:
    settings = get_settings()
    end = deadline or _deadline()
    poll = max(30, settings.owner_resolve_poll_seconds)
    attempts = 0
    listing = await repo.get_by_id(listing_id)
    if listing is None:
        return OwnerResolveOutcome(False, None, 0, "listing_not_found")

    if listing.owner_source == OwnerSource.MANUAL.value and listing.owner_name and listing.owner_phone:
        return OwnerResolveOutcome(True, listing, 0, "manual_owner_present")

    while datetime.now(UTC) < end:
        attempts += 1
        listing = await _refresh_listing_payload(repo, listing, requested_input)
        urls_before = len(collect_validation_urls(listing.raw_payload))
        patch = await run_owner_source_cycle(repo, listing)
        if patch:
            listing = await _persist_owner_patch(repo, listing, patch)
            if owner_complete(
                ListingPayload(
                    owner_name=listing.owner_name,
                    owner_phone=listing.owner_phone,
                )
            ):
                return OwnerResolveOutcome(True, listing, attempts, "owner_resolved")

        if (
            listing.owner_name
            and listing.owner_phone
            and not owner_matches_broker(
                listing.owner_name, listing.owner_phone, raw_payload=listing.raw_payload
            )
        ):
            return OwnerResolveOutcome(True, listing, attempts, "owner_resolved")

        log.info(
            "owner_resolve.waiting",
            listing_id=listing.id,
            attempt=attempts,
            validation_urls=urls_before,
            next_poll_seconds=poll,
        )
        await asyncio.sleep(poll)
        listing = await repo.get_by_id(listing_id)
        if listing is None:
            break

    return OwnerResolveOutcome(False, listing, attempts, "deadline_exceeded")


async def resolve_owner_for_input(repo: ListingRepository, text: str) -> OwnerResolveOutcome:
    req = parse_lookup_input(text)
    payload = await ExtractorChain().extract(req)
    listing = await repo.upsert_from_payload(payload.to_upsert(req))
    if req.source == "dld_phone":
        ok = bool(payload.owner_name and payload.owner_phone)
        return OwnerResolveOutcome(ok, listing, 0, "dld_phone_resolved" if ok else "dld_phone_incomplete")
    return await resolve_owner_for_listing(
        repo,
        listing_id=listing.id,
        requested_input=text,
    )