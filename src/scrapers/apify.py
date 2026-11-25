from __future__ import annotations

from typing import Any

import httpx

from config import get_settings
from scrapers.actor_maps import ApifyListingRecord
from scrapers.base import BaseExtractor
from scrapers.concurrency import source_concurrency
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload
from services.lookup_request import LookupRequest


class ApifyExtractor(BaseExtractor):
    name = "apify"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    def supports(self, req: LookupRequest) -> bool:
        return req.source in ("propertyfinder", "bayut")

    def _actor_id(self, source: str) -> str:
        settings = get_settings()
        actors = {
            "propertyfinder": settings.apify_actor_propertyfinder,
            "bayut": settings.apify_actor_bayut,
        }
        actor = actors.get(source, "").strip()
        if not actor:
            raise ExtractionError(
                code="actor_not_configured",
                message=f"apify actor missing for source={source}",
                extractor=self.name,
                source=source,
            )
        return actor

    async def _run_actor(self, req: LookupRequest) -> dict[str, Any]:
        settings = get_settings()
        actor_id = self._actor_id(req.source)
        url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
        body = {
            "url": req.raw_input.strip(),
            "listingId": req.external_id,
            "startUrls": [{"url": req.raw_input.strip()}],
        }

        async def _call() -> dict[str, Any]:
            client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(120.0))
            own_client = self._client is None
            try:
                response = await client.post(
                    url,
                    params={"token": settings.apify_token, "format": "json"},
                    json=body,
                )
                if response.status_code >= 400:
                    raise ExtractionError(
                        code="apify_http_error",
                        message=f"status={response.status_code}",
                        extractor=self.name,
                        source=req.source,
                    )
                data = response.json()
                if not isinstance(data, list) or not data:
                    raise ExtractionError(
                        code="apify_empty",
                        message="actor returned no items",
                        extractor=self.name,
                        source=req.source,
                    )
                item = data[0]
                if not isinstance(item, dict):
                    raise ExtractionError(
                        code="apify_invalid",
                        message="first dataset item is not an object",
                        extractor=self.name,
                        source=req.source,
                    )
                return item
            finally:
                if own_client:
                    await client.aclose()

        return await source_concurrency.run(req.source, _call)

    async def _fetch(self, req: LookupRequest) -> ListingPayload:
        item = await self._run_actor(req)
        record = ApifyListingRecord.model_validate(item)
        payload = record.to_listing_payload(source=req.source)
        if not payload.source_listing_id:
            payload = payload.model_copy(update={"source_listing_id": req.external_id})
        if not payload.source_url:
            payload = payload.model_copy(update={"source_url": req.raw_input.strip()})
        return payload