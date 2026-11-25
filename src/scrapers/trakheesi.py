from __future__ import annotations

import httpx

from config import get_settings
from scrapers.base import BaseExtractor
from scrapers.dld_permit import fetch_dld_for_request
from scrapers.payload import ListingPayload
from services.lookup_request import LookupRequest


class TrakheesiExtractor(BaseExtractor):
    name = "trakheesi"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    def supports(self, req: LookupRequest) -> bool:
        return req.source == "trakheesi"

    async def _fetch(self, req: LookupRequest) -> ListingPayload:
        get_settings()
        return await fetch_dld_for_request(req)