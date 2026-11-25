from __future__ import annotations

from urllib.parse import quote

import httpx

from config import get_settings
from scrapers.browser_headers import json_api_headers
from scrapers.concurrency import source_concurrency
from scrapers.direct import parse_listing_html
from scrapers.embed_json import extract_embedded_nodes
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload, merge_payloads
from services.lookup_request import LookupRequest
from services.owner_broker_guard import strip_broker_owner
from services.permit_candidates import extract_owner_fields_from_unknown

_DEFAULT_PATTERNS = (
    "https://www.propertyfinder.ae/api/pwa/property/{id}",
    "https://www.propertyfinder.ae/en/api/property/{id}",
    "https://www.propertyfinder.ae/property-api/v1/en/property/{id}",
    "https://www.propertyfinder.ae/api/pwa/property/search/v1/property/{id}",
)


def _api_patterns() -> list[str]:
    settings = get_settings()
    raw = (settings.pf_direct_api_urls or "").strip()
    if not raw:
        return list(_DEFAULT_PATTERNS)
    return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]


def _payload_from_json(data: dict, req: LookupRequest, *, url: str) -> ListingPayload:
    owner_name, owner_phone = extract_owner_fields_from_unknown(data)
    listing = data.get("listing") if isinstance(data.get("listing"), dict) else data.get("property")
    if isinstance(listing, dict):
        on, op = extract_owner_fields_from_unknown(listing)
        owner_name = owner_name or on
        owner_phone = owner_phone or op
    permit = None
    rera = data.get("rera") or (listing.get("rera") if isinstance(listing, dict) else None)
    if isinstance(rera, dict):
        permit = rera.get("issued_license_number") or rera.get("number") or rera.get("permitNumber")
    return ListingPayload(
        source=req.source,
        source_url=req.raw_input.strip(),
        source_listing_id=req.external_id,
        permit_number=str(permit).strip() if permit else None,
        owner_name=owner_name,
        owner_phone=owner_phone,
        raw_payload={"propertyfinder_api": {"url": url, "body": data}},
    )


async def fetch_propertyfinder_listing(req: LookupRequest) -> ListingPayload:
    listing_id = req.external_id.strip()
    if not listing_id:
        raise ExtractionError(
            code="pf_invalid_id",
            message="missing listing id",
            extractor="propertyfinder_api",
            source=req.source,
        )

    referer = req.raw_input.strip() if req.raw_input.startswith("http") else f"https://www.propertyfinder.ae/"
    headers = json_api_headers(referer=referer)
    encoded = quote(listing_id, safe="")
    last: ExtractionError | None = None

    async def _get(url: str) -> dict:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 404:
                raise ExtractionError(
                    code="pf_api_not_found",
                    message="not found",
                    extractor="propertyfinder_api",
                    source=req.source,
                )
            if response.status_code >= 400:
                raise ExtractionError(
                    code="pf_api_http_error",
                    message=f"status={response.status_code}",
                    extractor="propertyfinder_api",
                    source=req.source,
                )
            ctype = (response.headers.get("content-type") or "").lower()
            text = response.text
            if "json" in ctype or text.strip().startswith("{"):
                data = response.json()
                if not isinstance(data, dict):
                    raise ExtractionError(
                        code="pf_api_invalid",
                        message="response not object",
                        extractor="propertyfinder_api",
                        source=req.source,
                    )
                return data
            return {"html": text}

    for pattern in _api_patterns():
        url = pattern.format(id=encoded)
        try:

            async def _call(u: str = url) -> dict:
                return await _get(u)

            data = await source_concurrency.run("propertyfinder", _call)
            if "html" in data and len(data) == 1:
                html = str(data["html"])
                nodes = extract_embedded_nodes(html)
                if nodes:
                    owner_name, owner_phone = extract_owner_fields_from_unknown(nodes)
                    if owner_name or owner_phone:
                        patch = ListingPayload(
                            source=req.source,
                            source_listing_id=listing_id,
                            owner_name=owner_name,
                            owner_phone=owner_phone,
                            raw_payload={"propertyfinder_api": {"url": url, "embedded_nodes": len(nodes)}},
                        )
                        return strip_broker_owner(patch)
                patch = parse_listing_html(html, req)
                return strip_broker_owner(
                    merge_payloads(patch, patch.model_copy(update={"raw_payload": {"propertyfinder_api": {"url": url}}}))
                )
            patch = _payload_from_json(data, req, url=url)
            if not patch.owner_name and not patch.owner_phone and not patch.permit_number:
                raise ExtractionError(
                    code="pf_api_empty",
                    message="no owner or permit in json",
                    extractor="propertyfinder_api",
                    source=req.source,
                )
            return strip_broker_owner(patch)
        except ExtractionError as exc:
            last = exc

    if last:
        raise last
    raise ExtractionError(
        code="pf_api_exhausted",
        message="all propertyfinder api urls failed",
        extractor="propertyfinder_api",
        source=req.source,
    )