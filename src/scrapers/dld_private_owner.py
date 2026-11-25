from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from config import get_settings
from scrapers.actor_maps import MadmounIntegrationRecord
from scrapers.concurrency import source_concurrency
from scrapers.dld_private_client import merge_post_body, trakheesi_auth_headers
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload
from scrapers.trakheesi_runtime import load_trakheesi_public_config
from services.owner_broker_guard import strip_broker_owner
from services.permit_candidates import extract_owner_fields_from_unknown

_DEFAULT_PRIVATE_URLS = (
    "https://b2c.dubailand.gov.ae/mv-portal-service/private/property/{key}",
    "https://b2c.dubailand.gov.ae/mv-portal-service/private/owner/{key}",
    "https://b2c.dubailand.gov.ae/trakheesi/core/api/private/property/{key}",
    "https://ext.dubailand.gov.ae/trakheesi/private/property/{key}",
)


def _url_templates() -> list[str]:
    settings = get_settings()
    raw = (settings.dld_private_owner_urls or "").strip()
    if not raw:
        return list(_DEFAULT_PRIVATE_URLS)
    return [u.strip() for u in raw.replace(";", ",").split(",") if u.strip()]


def _payload_from_data(data: dict[str, Any], *, source: str, meta: dict[str, Any]) -> ListingPayload:
    owner_name, owner_phone = extract_owner_fields_from_unknown(data)
    record: MadmounIntegrationRecord | None = None
    try:
        record = MadmounIntegrationRecord.model_validate(data)
    except Exception:
        record = None
    if record and record.owner_name:
        owner_name = owner_name or record.owner_name
    if record and record.owner_phone:
        owner_phone = owner_phone or record.owner_phone
    if not owner_name and not owner_phone:
        raise ExtractionError(
            code="dld_private_empty",
            message="private response has no owner fields",
            extractor="dld_private",
            source=source,
        )
    payload = ListingPayload(
        source=source,
        owner_name=owner_name,
        owner_phone=owner_phone,
        permit_number=record.license_number if record else None,
        unit_number=record.property_number if record else None,
        building=(record.building_name_en or record.building_name_ar) if record else None,
        raw_payload={"dld_private": {**meta, "body": data}},
    )
    return strip_broker_owner(payload)


async def _get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    async def _call() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0), follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 404:
                raise ExtractionError(
                    code="dld_private_not_found",
                    message="not found",
                    extractor="dld_private",
                    source="dld",
                )
            if response.status_code >= 400:
                raise ExtractionError(
                    code="dld_private_http_error",
                    message=f"status={response.status_code}",
                    extractor="dld_private",
                    source="dld",
                )
            data = response.json()
            if isinstance(data, dict) and isinstance(data.get("data"), dict):
                return data["data"]
            if isinstance(data, dict) and isinstance(data.get("Response"), dict):
                return data["Response"]
            if isinstance(data, dict) and isinstance(data.get("result"), dict):
                return data["result"]
            if not isinstance(data, dict):
                raise ExtractionError(
                    code="dld_private_invalid",
                    message="not an object",
                    extractor="dld_private",
                    source="dld",
                )
            return data

    return await source_concurrency.run("trakheesi", _call)


async def _post_json(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    async def _call() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0), follow_redirects=True) as client:
            response = await client.post(url, json=body, headers=headers)
            if response.status_code == 404:
                raise ExtractionError(
                    code="dld_private_not_found",
                    message="not found",
                    extractor="dld_private",
                    source="dld",
                )
            if response.status_code >= 400:
                raise ExtractionError(
                    code="dld_private_http_error",
                    message=f"status={response.status_code}",
                    extractor="dld_private",
                    source="dld",
                )
            data = response.json()
            if not isinstance(data, dict):
                raise ExtractionError(
                    code="dld_private_invalid",
                    message="not an object",
                    extractor="dld_private",
                    source="dld",
                )
            return data

    return await source_concurrency.run("trakheesi", _call)


async def fetch_trakheesi_revamp_owner(guid: str) -> ListingPayload:
    settings = get_settings()
    config = await load_trakheesi_public_config()
    base = (settings.trakheesi_revamp_api_base or config.revamp_api_base).rstrip("/")
    path = config.validate_guid_path.lstrip("/")
    url = f"{base}/{path}"
    headers = trakheesi_auth_headers(config)
    body = merge_post_body({"ListingGUID": guid}, config)

    data = await _post_json(url, body, headers)
    normalized = data.get("result") if isinstance(data.get("result"), dict) else data
    if isinstance(data.get("Response"), dict):
        normalized = data["Response"]
    if not isinstance(normalized, dict):
        normalized = data
    return _payload_from_data(
        normalized,
        source="trakheesi",
        meta={"method": "revamp_validate_guid", "url": url, "guid": guid},
    )


async def _auth_headers() -> dict[str, str]:
    settings = get_settings()
    if settings.trakheesi_integration_consumer_id and settings.trakheesi_listing_guid_auth_key:
        return trakheesi_auth_headers(None)
    config = await load_trakheesi_public_config()
    return trakheesi_auth_headers(config)


async def fetch_dld_private_owner_by_key(lookup_key: str) -> ListingPayload:
    headers = await _auth_headers()
    encoded = quote(lookup_key, safe="")
    last: ExtractionError | None = None

    for template in _url_templates():
        if "{key}" not in template:
            continue
        url = template.format(key=encoded)
        try:
            data = await _get_json(url, headers)
            return _payload_from_data(data, source="dld", meta={"url": url, "lookup_key": lookup_key})
        except ExtractionError as exc:
            last = exc
    if last:
        raise last
    raise ExtractionError(
        code="dld_private_not_configured",
        message="no private owner URLs",
        extractor="dld_private",
        source="dld",
    )


async def resolve_owner_via_dld_private(
    *,
    listing_guid: str | None,
    real_estate_number: str | None,
    property_id: str | None,
    transaction_number: str | None,
) -> ListingPayload:
    if listing_guid:
        try:
            return await fetch_trakheesi_revamp_owner(listing_guid)
        except ExtractionError:
            pass

    for key in (real_estate_number, property_id, transaction_number, listing_guid):
        if not key or str(key).strip() in {"", "-1", "0"}:
            continue
        try:
            return await fetch_dld_private_owner_by_key(str(key).strip())
        except ExtractionError:
            continue

    raise ExtractionError(
        code="dld_private_exhausted",
        message="all private owner lookups failed",
        extractor="dld_private",
        source="dld",
    )