from __future__ import annotations

from dataclasses import dataclass

from db.models import Listing
from db.repository import ListingRepository
from db.session import session_scope
from scrapers.chain import ExtractorChain
from services.input_parser import InputParseError, parse_lookup_input
from services.listing_resolve import ListingResolveService
from services.lookup_request import LookupRequest


@dataclass(frozen=True)
class LookupOutcome:
    listing: Listing
    cache_hit: bool
    request: LookupRequest


class LookupOrchestrator:
    def __init__(self, chain: ExtractorChain | None = None) -> None:
        self._chain = chain or ExtractorChain()

    async def run(self, *, telegram_user_id: int, text: str, force_refresh: bool = False) -> LookupOutcome:
        req = parse_lookup_input(text)

        async with session_scope() as session:
            from config import get_settings

            settings = get_settings()
            repo = ListingRepository(session, cache_ttl_days=settings.cache_ttl_days)
            resolver = ListingResolveService(repo)

            async def extract():
                payload = await self._chain.extract(req)
                return payload.to_upsert(req)

            if req.source == "trakheesi":
                result = await resolver.resolve_by_permit(
                    permit_number=req.external_id,
                    telegram_user_id=telegram_user_id,
                    requested_input=req.raw_input,
                    extract=extract,
                    force_refresh=force_refresh,
                )
            else:
                result = await resolver.resolve_by_source_id(
                    source=req.source,
                    source_listing_id=req.external_id,
                    telegram_user_id=telegram_user_id,
                    requested_input=req.raw_input,
                    extract=extract,
                    force_refresh=force_refresh,
                )

            return LookupOutcome(
                listing=result.listing,
                cache_hit=result.cache_hit,
                request=req,
            )

    async def run_for_listing(
        self,
        *,
        telegram_user_id: int,
        listing: Listing,
        force_refresh: bool = True,
    ) -> LookupOutcome:
        if listing.source == "trakheesi":
            text = listing.permit_number or str(listing.id)
        else:
            text = listing.source_url or f"{listing.source}:{listing.source_listing_id}"
        return await self.run(
            telegram_user_id=telegram_user_id,
            text=text,
            force_refresh=force_refresh,
        )


def parse_user_input(text: str) -> LookupRequest:
    return parse_lookup_input(text)


__all__ = ["InputParseError", "LookupOrchestrator", "LookupOutcome", "parse_user_input"]