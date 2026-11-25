from __future__ import annotations

import httpx

from config import get_settings
from scrapers.actor_maps import DldPermitRecord
from scrapers.concurrency import source_concurrency
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload
from services.lookup_request import LookupRequest


async def fetch_dld_permit_by_digits(permit_digits: str) -> ListingPayload:
    settings = get_settings()
    base = settings.dld_permit_api_url.rstrip("/")
    if not base:
        raise ExtractionError(
            code="dld_not_configured",
            message="DLD_PERMIT_API_URL missing",
            extractor="dld",
            source="trakheesi",
        )

    async def _call() -> dict:
        client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        try:
            response = await client.get(
                f"{base}/{permit_digits}",
                headers={"Accept": "application/json"},
            )
            if response.status_code == 404:
                raise ExtractionError(
                    code="permit_not_found",
                    message="permit not found",
                    extractor="dld",
                    source="trakheesi",
                )
            if response.status_code >= 400:
                raise ExtractionError(
                    code="dld_http_error",
                    message=f"status={response.status_code}",
                    extractor="dld",
                    source="trakheesi",
                )
            data = response.json()
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
                data = data["data"]
            if not isinstance(data, dict):
                raise ExtractionError(
                    code="dld_invalid",
                    message="response is not an object",
                    extractor="dld",
                    source="trakheesi",
                )
            return data
        finally:
            await client.aclose()

    data = await source_concurrency.run("trakheesi", _call)
    record = DldPermitRecord.model_validate(data)
    payload = record.to_listing_payload()
    if not payload.permit_number:
        payload = payload.model_copy(update={"permit_number": permit_digits})
    return payload


async def fetch_dld_for_request(req: LookupRequest) -> ListingPayload:
    return await fetch_dld_permit_by_digits(req.external_id)