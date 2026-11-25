from __future__ import annotations

from scrapers.base import BaseExtractor
from scrapers.payload import ListingPayload
from services.lookup_request import LookupRequest
class DldPhoneExtractor(BaseExtractor):
    name = "dld_phone"

    def supports(self, req: LookupRequest) -> bool:
        return req.source == "dld_phone"

    async def _fetch(self, req: LookupRequest) -> ListingPayload:
        from services.owner_phone_lookup import resolve_owner_by_dld_phone

        return await resolve_owner_by_dld_phone(req.external_id)