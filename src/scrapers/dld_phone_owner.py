from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from config import get_settings
from scrapers.concurrency import source_concurrency
from scrapers.dld_private_client import merge_post_body, trakheesi_auth_headers
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload
from scrapers.trakheesi_runtime import load_trakheesi_public_config
from services.owner_broker_guard import strip_broker_owner
from services.permit_candidates import extract_owner_fields_from_unknown
from services.uae_phone import canonical_uae_mobile, uae_phone_variants

_DEFAULT_GET = (
    "https://b2c.dubailand.gov.ae/mv-portal-service/private/owner/mobile/{phone}",
    "https://b2c.dubailand.gov.ae/mv-portal-service/private/subscriber/mobile/{phone}",
    "https://b2c.dubailand.gov.ae/mv-portal-service/public/owner/mobile/{phone}",
    "https://b2c.dubailand.gov.ae/mv-portal-service/private/property-owner/mobile/{phone}",
    "https://b2c.dubailand.gov.ae/trakheesi/core/api/private/owner/mobile/{phone}",
)

_DEFAULT_POST = (
    "https://b2c.dubailand.gov.ae/mv-portal-service/private/subscriber/owner",
    "https://b2c.dubailand.gov.ae/trakheesi/core/api/private/owner/by-mobile",
    "https://ext.dubailand.gov.ae/trakheesi/private/owner/mobile",
)


def _parse_urls(raw: str, default: tuple[str, ...]) -> list[str]:
    if raw.strip() == "-":
        return []
    if not raw.strip():
        return list(default)
    return [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]


def _coerce_payload(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        for key in ("data", "result", "Response", "response"):
            inner = data.get(key)
            if isinstance(inner, dict):
                return inner
        return data
    return {}


def _payload_from_body(data: dict[str, Any], *, phone: str, meta: dict[str, Any]) -> ListingPayload:
    owner_name, owner_phone = extract_owner_fields_from_unknown(data)
    if not owner_phone:
        owner_phone = canonical_uae_mobile(phone) or phone
    if not owner_name and not owner_phone:
        raise ExtractionError(
            code="dld_phone_empty",
            message="no owner in phone lookup response",
            extractor="dld_phone",
            source="dld",
        )
    payload = ListingPayload(
        source="dld",
        owner_name=owner_name,
        owner_phone=owner_phone or canonical_uae_mobile(phone),
        raw_payload={"dld_phone_owner": {**meta, "body": data}},
    )
    permit = data.get("licenseNumber") or data.get("LicenseNumber") or data.get("permit_number")
    if permit:
        payload = payload.model_copy(update={"permit_number": str(permit).strip()})
    building = data.get("buildingNameEn") or data.get("BuildingNameEn") or data.get("building")
    if building:
        payload = payload.model_copy(update={"building": str(building).strip()})
    return strip_broker_owner(payload)


async def _get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    async def _call() -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(25.0), follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise ExtractionError(
                code="dld_phone_connect_error",
                message=str(exc),
                extractor="dld_phone",
                source="dld",
            ) from exc
        if response.status_code == 404:
            raise ExtractionError(
                code="dld_phone_not_found",
                message="not found",
                extractor="dld_phone",
                source="dld",
            )
        if response.status_code >= 400:
            raise ExtractionError(
                code="dld_phone_http_error",
                message=f"status={response.status_code}",
                extractor="dld_phone",
                source="dld",
            )
        parsed = response.json()
        data = _coerce_payload(parsed) if isinstance(parsed, dict) else {}
        if not data and isinstance(parsed, dict):
            data = parsed
        return data

    return await source_concurrency.run("trakheesi", _call)


async def _post_json(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    async def _call() -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(25.0), follow_redirects=True) as client:
                response = await client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise ExtractionError(
                code="dld_phone_connect_error",
                message=str(exc),
                extractor="dld_phone",
                source="dld",
            ) from exc
        if response.status_code == 404:
            raise ExtractionError(
                code="dld_phone_not_found",
                message="not found",
                extractor="dld_phone",
                source="dld",
            )
        if response.status_code >= 400:
            raise ExtractionError(
                code="dld_phone_http_error",
                message=f"status={response.status_code}",
                extractor="dld_phone",
                source="dld",
            )
        parsed = response.json()
        data = _coerce_payload(parsed) if isinstance(parsed, dict) else {}
        if not data and isinstance(parsed, dict):
            data = parsed
        return data

    return await source_concurrency.run("trakheesi", _call)


async def fetch_dld_owner_by_phone(phone: str) -> ListingPayload:
    canonical = canonical_uae_mobile(phone)
    if not canonical:
        raise ExtractionError(
            code="dld_phone_invalid",
            message="not a UAE mobile number",
            extractor="dld_phone",
            source="dld",
        )

    settings = get_settings()
    config = await load_trakheesi_public_config()
    headers = trakheesi_auth_headers(config)
    subscriber = (settings.dld_subscriber_mobile or "").strip()
    if subscriber:
        headers.setdefault("X-Subscriber-Mobile", canonical_uae_mobile(subscriber) or subscriber)

    get_templates = _parse_urls(settings.dld_owner_phone_api_urls, _DEFAULT_GET)
    last: ExtractionError | None = None

    local = canonical[3:]
    url_variants = list(
        dict.fromkeys(
            [canonical, f"+{canonical}", local, f"0{local}", f"00{canonical}"],
        )
    )
    tried: set[str] = set()
    for variant in url_variants:
        encoded = quote(variant, safe="")
        if encoded in tried:
            continue
        tried.add(encoded)
        for template in get_templates:
            if "{phone}" not in template:
                continue
            url = template.format(phone=encoded)
            try:
                data = await _get_json(url, headers)
                return _payload_from_body(data, phone=canonical, meta={"url": url, "method": "GET"})
            except ExtractionError as exc:
                last = exc
            if last and last.code == "dld_phone_not_found":
                break

    post_templates = _parse_urls(settings.dld_owner_phone_post_urls, _DEFAULT_POST)
    bodies = [
        {"MobileNumber": canonical, "mobileNumber": canonical, "mobile": canonical, "Mobile": canonical},
        merge_post_body({"MobileNumber": canonical, "Mobile": f"+{canonical}"}, config),
    ]
    for template in post_templates:
        for body in bodies:
            try:
                data = await _post_json(template, body, headers)
                return _payload_from_body(data, phone=canonical, meta={"url": template, "method": "POST"})
            except ExtractionError as exc:
                last = exc

    if last:
        raise last
    raise ExtractionError(
        code="dld_phone_exhausted",
        message="all phone owner endpoints failed",
        extractor="dld_phone",
        source="dld",
    )