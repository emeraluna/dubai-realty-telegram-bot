from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from db.models import Listing
from db.repository import ListingRepository
from db.schemas import ListingUpsertPayload

ExtractFn = Callable[[], Awaitable[ListingUpsertPayload]]


@dataclass(frozen=True)
class ResolveResult:
    listing: Listing
    cache_hit: bool


class ListingResolveService:
    def __init__(self, repo: ListingRepository) -> None:
        self._repo = repo

    async def resolve_by_source_id(
        self,
        *,
        source: str,
        source_listing_id: str,
        telegram_user_id: int,
        requested_input: str,
        extract: ExtractFn,
        force_refresh: bool = False,
    ) -> ResolveResult:
        listing = await self._repo.get_by_source_id(source, source_listing_id)
        if not force_refresh and listing is not None and self._repo.is_cache_fresh(listing):
            listing = await self._repo.bump_cache_hit(listing)
            await self._repo.record_lookup(
                listing_id=listing.id,
                telegram_user_id=telegram_user_id,
                requested_input=requested_input,
                cache_hit=True,
            )
            return ResolveResult(listing=listing, cache_hit=True)

        payload = await extract()
        listing = await self._repo.upsert_from_payload(payload)
        await self._repo.record_lookup(
            listing_id=listing.id,
            telegram_user_id=telegram_user_id,
            requested_input=requested_input,
            cache_hit=False,
        )
        return ResolveResult(listing=listing, cache_hit=False)

    async def resolve_by_permit(
        self,
        *,
        permit_number: str,
        telegram_user_id: int,
        requested_input: str,
        extract: ExtractFn,
        force_refresh: bool = False,
    ) -> ResolveResult:
        listing = await self._repo.get_by_permit(permit_number)
        if not force_refresh and listing is not None and self._repo.is_cache_fresh(listing):
            listing = await self._repo.bump_cache_hit(listing)
            await self._repo.record_lookup(
                listing_id=listing.id,
                telegram_user_id=telegram_user_id,
                requested_input=requested_input,
                cache_hit=True,
            )
            return ResolveResult(listing=listing, cache_hit=True)

        payload = await extract()
        listing = await self._repo.upsert_from_payload(payload)
        await self._repo.record_lookup(
            listing_id=listing.id,
            telegram_user_id=telegram_user_id,
            requested_input=requested_input,
            cache_hit=False,
        )
        return ResolveResult(listing=listing, cache_hit=False)