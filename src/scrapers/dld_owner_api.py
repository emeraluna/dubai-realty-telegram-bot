from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

from config import get_settings
from scrapers.actor_maps import DldPermitRecord, MadmounIntegrationRecord
from scrapers.concurrency import source_concurrency
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload
from services.permit_candidates import extract_owner_fields_from_unknown

_DEFAULT_URL_TEMPLATES = (
    "https://b2c.dubailand.gov.ae/mv-portal-service/public/permit/{key}",
    "https://b2c.dubailand.gov.ae/mv-portal-service/public/listing/{key}",
    "https://b2c.dubailand.gov.ae/mv-portal-service/public/transaction/{key}",
    "https://b2c.dubailand.gov.ae/mv-portal-service/public/property/{key}",
    "https://b2c.dubailand.gov.ae/mv-portal-service/public/real-estate/{key}",
    "https://b2c.dubailand.gov.ae/trakheesi/core/api/public/property/{key}",
    "https://b2c.dubailand.gov.ae/trakheesi/core/api/public/permit/{key}",
)


def _parse_owner_urls_env(raw: str) -> list[str]:
    if not raw.strip():
        return list(_DEFAULT_URL_TEMPLATES)
    return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]


def _coerce_payload(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], dict):
            return data["data"]
        if "result" in data and isinstance(data["result"], dict):
            return data["result"]
        return data
    return {}


async def _fetch_json_url(url: str) -> dict[str, Any]:
    settings = get_settings()
    headers = {
        "Accept": "application/json",
        "User-Agent": "dubai-realty-bot/0.1",
    }
    if settings.trakheesi_integration_consumer_id:
        headers["consumer-id"] = settings.trakheesi_integration_consumer_id
    if settings.trakheesi_session_token:
        headers["Token"] = settings.trakheesi_session_token

    async def _call() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 404:
                raise ExtractionError(
                    code="dld_owner_not_found",
                    message="not found",
                    extractor="dld_owner",
                    source="trakheesi",
                )
            if response.status_code >= 400:
                raise ExtractionError(
                    code="dld_owner_http_error",
                    message=f"status={response.status_code}",
                    extractor="dld_owner",
                    source="trakheesi",
                )
            data = response.json()
            return _coerce_payload(data)

    return await source_concurrency.run("trakheesi", _call)


def _payload_from_record(data: dict[str, Any], *, lookup_key: str, url: str) -> ListingPayload:
    try:
        record = DldPermitRecord.model_validate(data)
        payload = record.to_listing_payload()
    except Exception:
        owner_name, owner_phone = extract_owner_fields_from_unknown(data)
        try:
            madmoun = MadmounIntegrationRecord.model_validate(data)
            payload = madmoun.to_listing_payload()
        except Exception:
            payload = ListingPayload(
                source="trakheesi",
                owner_name=owner_name,
                owner_phone=owner_phone,
            )

    if not payload.owner_name and not payload.owner_phone:
        raise ExtractionError(
            code="dld_owner_empty",
            message="no owner fields in response",
            extractor="dld_owner",
            source="trakheesi",
        )
    raw = dict(payload.raw_payload or {})
    raw["dld_owner_api"] = {"lookup_key": lookup_key, "url": url, "body": data}
    return payload.model_copy(update={"raw_payload": raw})


async def fetch_dld_owner_by_key(lookup_key: str) -> ListingPayload:
    key = re.sub(r"\D", "", lookup_key) or lookup_key.strip()
    if not key:
        raise ExtractionError(
            code="dld_owner_invalid_key",
            message="empty lookup key",
            extractor="dld_owner",
            source="trakheesi",
        )

    settings = get_settings()
    templates = _parse_owner_urls_env(settings.dld_owner_api_urls)
    encoded = quote(key, safe="")
    last_error: ExtractionError | None = None

    for template in templates:
        if "{key}" not in template:
            continue
        url = template.format(key=encoded)
        try:
            data = await _fetch_json_url(url)
            return _payload_from_record(data, lookup_key=key, url=url)
        except ExtractionError as exc:
            last_error = exc
            if exc.code not in {"dld_owner_not_found", "dld_owner_http_error", "dld_owner_empty"}:
                raise

    if last_error:
        raise last_error
    raise ExtractionError(
        code="dld_owner_not_configured",
        message="no DLD owner API URLs configured",
        extractor="dld_owner",
        source="trakheesi",
    )