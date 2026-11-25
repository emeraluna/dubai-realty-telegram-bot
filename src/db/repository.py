from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.enums import OwnerSource
from db.models import Listing, Lookup
from db.schemas import ListingUpsertPayload

log = structlog.get_logger(__name__)

OWNER_FIELDS = frozenset({"owner_name", "owner_phone"})


class ListingRepository:
    def __init__(self, session: AsyncSession, *, cache_ttl_days: int) -> None:
        self._session = session
        self._cache_ttl_days = cache_ttl_days

    def cache_ttl(self) -> timedelta:
        return timedelta(days=self._cache_ttl_days)

    def is_cache_fresh(self, listing: Listing, *, now: datetime | None = None) -> bool:
        ref = now or datetime.now(UTC)
        last = listing.last_seen_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        return ref - last <= self.cache_ttl()

    async def get_by_source_id(self, source: str, source_listing_id: str) -> Listing | None:
        stmt = select(Listing).where(
            Listing.source == source,
            Listing.source_listing_id == source_listing_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_permit(self, permit_number: str) -> Listing | None:
        stmt = select(Listing).where(Listing.permit_number == permit_number)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_source_url(self, source_url: str) -> Listing | None:
        stmt = select(Listing).where(Listing.source_url == source_url)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_unit_and_building(self, unit_number: str, building: str) -> Listing | None:
        stmt = select(Listing).where(
            Listing.unit_number == unit_number,
            Listing.building == building,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, listing_id: int) -> Listing | None:
        stmt = select(Listing).where(Listing.id == listing_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def listings_by_owner_phone(self, phone: str) -> list[Listing]:
        from services.uae_phone import digits_only, uae_phone_variants

        needles = {digits_only(v) for v in uae_phone_variants(phone)}
        if not needles:
            return []
        stmt = select(Listing).where(Listing.owner_phone.is_not(None))
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        return [row for row in rows if digits_only(row.owner_phone or "") in needles]

    async def user_stats(self, telegram_user_id: int) -> dict[str, int]:
        total_stmt = select(func.count(Lookup.id)).where(Lookup.telegram_user_id == telegram_user_id)
        hits_stmt = (
            select(func.count(Lookup.id))
            .where(Lookup.telegram_user_id == telegram_user_id)
            .where(Lookup.cache_hit.is_(True))
        )
        listings_stmt = (
            select(func.count(func.distinct(Lookup.listing_id)))
            .where(Lookup.telegram_user_id == telegram_user_id)
        )
        total = int((await self._session.execute(total_stmt)).scalar_one())
        cache_hits = int((await self._session.execute(hits_stmt)).scalar_one())
        listings = int((await self._session.execute(listings_stmt)).scalar_one())
        return {
            "lookups_total": total,
            "cache_hits": cache_hits,
            "listings_archived": listings,
            "extractions_saved": cache_hits,
        }

    async def listings_for_user_export(self, telegram_user_id: int) -> list[Listing]:
        subq = (
            select(
                Lookup.listing_id.label("listing_id"),
                func.max(Lookup.created_at).label("last_lookup_at"),
            )
            .where(Lookup.telegram_user_id == telegram_user_id)
            .group_by(Lookup.listing_id)
            .subquery()
        )
        stmt = (
            select(Listing)
            .join(subq, Listing.id == subq.c.listing_id)
            .order_by(subq.c.last_lookup_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    def _apply_scraped_owner_rules(self, existing: Listing, data: dict[str, Any]) -> None:
        if existing.owner_source != OwnerSource.MANUAL.value:
            clearing = (
                "owner_name" in data
                and "owner_phone" in data
                and not data.get("owner_name")
                and not data.get("owner_phone")
            )
            if clearing:
                existing.owner_name = None
                existing.owner_phone = None
                existing.owner_source = OwnerSource.UNKNOWN.value
                return
            for key in OWNER_FIELDS:
                if data.get(key):
                    setattr(existing, key, data[key])
            if data.get("owner_name") or data.get("owner_phone"):
                existing.owner_source = OwnerSource.SCRAPED.value
            return

        for key in OWNER_FIELDS:
            incoming = data.get(key)
            if incoming is None:
                continue
            current = getattr(existing, key)
            if current and str(current).strip() and str(current).strip() != str(incoming).strip():
                log.info(
                    "owner_override_suppressed",
                    listing_id=existing.id,
                    field=key,
                    manual_value=current,
                    scraped_value=incoming,
                )
                continue
            if not current or not str(current).strip():
                setattr(existing, key, incoming)

    async def upsert_from_payload(self, payload: ListingUpsertPayload) -> Listing:
        now = datetime.now(UTC)
        data = payload.model_dump()
        raw_payload = data.pop("raw_payload", {}) or {}
        data.pop("owner_source", None)
        data.pop("owner_updated_at", None)

        existing: Listing | None = None
        if payload.source_listing_id:
            existing = await self.get_by_source_id(payload.source, payload.source_listing_id)
        if existing is None and payload.permit_number:
            existing = await self.get_by_permit(payload.permit_number)

        if existing is None:
            owner_source = OwnerSource.UNKNOWN.value
            if data.get("owner_name") or data.get("owner_phone"):
                owner_source = OwnerSource.SCRAPED.value
            listing = Listing(
                **data,
                owner_source=owner_source,
                raw_payload=raw_payload,
                first_seen_at=now,
                last_seen_at=now,
                lookup_count=0,
            )
            self._session.add(listing)
            await self._session.flush()
            return listing

        owner_data = {k: data[k] for k in OWNER_FIELDS if k in data}
        for k in OWNER_FIELDS:
            data.pop(k, None)
        for key, value in data.items():
            if value is not None:
                setattr(existing, key, value)
        data.update(owner_data)
        self._apply_scraped_owner_rules(existing, data)
        existing.raw_payload = raw_payload
        existing.last_seen_at = now
        await self._session.flush()
        return existing

    async def upsert_manual_owner(
        self,
        listing: Listing | None,
        fields: dict[str, Any],
        *,
        batch_id: int | None = None,
    ) -> tuple[Listing, str]:
        now = datetime.now(UTC)
        owner_keys = {"owner_name", "owner_phone"}
        non_owner_fillable = {
            "unit_number",
            "floor",
            "building",
            "community",
            "developer",
            "size_sqft",
            "plot_number",
            "permit_number",
            "permit_status",
            "source_url",
            "source_listing_id",
        }

        if listing is None:
            source_listing_id = fields.get("source_listing_id") or fields.get("permit_number")
            listing = Listing(
                source="manual",
                source_listing_id=str(source_listing_id) if source_listing_id else None,
                source_url=fields.get("source_url"),
                unit_number=fields.get("unit_number"),
                floor=fields.get("floor"),
                building=fields.get("building"),
                community=fields.get("community"),
                developer=fields.get("developer"),
                size_sqft=fields.get("size_sqft"),
                plot_number=fields.get("plot_number"),
                permit_number=fields.get("permit_number"),
                permit_status=fields.get("permit_status"),
                owner_name=fields.get("owner_name"),
                owner_phone=fields.get("owner_phone"),
                owner_source=OwnerSource.MANUAL.value,
                owner_updated_at=now,
                raw_payload={"import_batch_id": batch_id} if batch_id else {},
                first_seen_at=now,
                last_seen_at=now,
                lookup_count=0,
            )
            self._session.add(listing)
            await self._session.flush()
            return listing, "inserted"

        changed = False
        skipped = True

        for key in owner_keys:
            incoming = fields.get(key)
            if incoming is None or str(incoming).strip() == "":
                continue
            if getattr(listing, key) != incoming:
                setattr(listing, key, incoming)
                changed = True
            skipped = False

        listing.owner_source = OwnerSource.MANUAL.value
        listing.owner_updated_at = now

        for key in non_owner_fillable:
            incoming = fields.get(key)
            if incoming is None or (isinstance(incoming, str) and not incoming.strip()):
                continue
            current = getattr(listing, key)
            if listing.owner_source == OwnerSource.MANUAL.value:
                setattr(listing, key, incoming)
                changed = True
                skipped = False
            elif current is None or (isinstance(current, str) and not str(current).strip()):
                setattr(listing, key, incoming)
                changed = True
                skipped = False

        await self._session.flush()
        if not changed and skipped:
            return listing, "skipped"
        return listing, "updated"

    async def bump_cache_hit(self, listing: Listing, *, now: datetime | None = None) -> Listing:
        ref = now or datetime.now(UTC)
        listing.lookup_count += 1
        listing.last_seen_at = ref
        await self._session.flush()
        await self._session.refresh(listing)
        return listing

    async def record_lookup(
        self,
        *,
        listing_id: int,
        telegram_user_id: int,
        requested_input: str,
        cache_hit: bool,
    ) -> Lookup:
        lookup = Lookup(
            listing_id=listing_id,
            telegram_user_id=telegram_user_id,
            requested_input=requested_input,
            cache_hit=cache_hit,
        )
        self._session.add(lookup)
        await self._session.flush()
        return lookup