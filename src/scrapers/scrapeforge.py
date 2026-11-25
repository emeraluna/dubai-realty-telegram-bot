from __future__ import annotations

from typing import Any

import httpx

from config import get_settings
from scrapers.actor_maps import ScrapeForgeListingRecord
from scrapers.base import BaseExtractor
from scrapers.concurrency import source_concurrency
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload
from services.lookup_request import LookupRequest


class ScrapeForgeExtractor(BaseExtractor):
    name = "scrapeforge"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    def supports(self, req: LookupRequest) -> bool:
        return req.source in ("propertyfinder", "bayut")

    async def _fetch(self, req: LookupRequest) -> ListingPayload:
        settings = get_settings()
        base = settings.scrapeforge_base_url.rstrip("/")
        if not base:
            raise ExtractionError(
                code="scrapeforge_not_configured",
                message="SCRAPEFORGE_BASE_URL missing",
                extractor=self.name,
                source=req.source,
            )

        async def _call() -> dict[str, Any]:
            client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(90.0))
            own_client = self._client is None
            try:
                response = await client.post(
                    f"{base}/v1/scrape/listing",
                    headers={
                        "Authorization": f"Bearer {settings.scrapeforge_key}",
                        "X-API-Key": settings.scrapeforge_key,
                    },
                    json={
                        "source": req.source,
                        "url": req.raw_input.strip(),
                        "listing_id": req.external_id,
                    },
                )
                if response.status_code >= 400:
                    raise ExtractionError(
                        code="scrapeforge_http_error",
                        message=f"status={response.status_code}",
                        extractor=self.name,
                        source=req.source,
                    )
                data = response.json()
                if not isinstance(data, dict):
                    raise ExtractionError(
                        code="scrapeforge_invalid",
                        message="response is not an object",
                        extractor=self.name,
                        source=req.source,
                    )
                return data
            finally:
                if own_client:
                    await client.aclose()

        item = await source_concurrency.run(req.source, _call)
        record = ScrapeForgeListingRecord.model_validate(item)
        payload = record.to_listing_payload(source=req.source)
        if not payload.source_listing_id:
            payload = payload.model_copy(update={"source_listing_id": req.external_id})
        if not payload.source_url:
            payload = payload.model_copy(update={"source_url": req.raw_input.strip()})
        return payload