from __future__ import annotations

import json
from typing import Any

import httpx

from config import get_settings
from scrapers.actor_maps import MadmounBrokerRecord, MadmounIntegrationRecord
from scrapers.concurrency import source_concurrency
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload
from scrapers.trakheesi_recaptcha import fetch_listing_validation_captcha
from scrapers.trakheesi_runtime import load_trakheesi_public_config
from services.owner_broker_guard import strip_broker_owner
from services.permit_candidates import extract_owner_fields_from_unknown


def normalize_integration_body(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("Response"), dict):
        return data["Response"]
    if isinstance(data.get("result"), dict):
        return data["result"]
    return data


async def post_madmoun_integration(guid: str, *, page_url: str) -> dict[str, Any]:
    settings = get_settings()
    config = await load_trakheesi_public_config()
    captcha = await fetch_listing_validation_captcha(page_url)
    if not captcha:
        raise ExtractionError(
            code="madmoun_captcha_required",
            message="set CAPTCHA_API_KEY for integration POST",
            extractor="madmoun",
            source="trakheesi",
        )

    post_url = (
        f"{(settings.trakheesi_integration_api_base or config.integration_api_base).rstrip('/')}"
        f"/{config.integration_post_path.lstrip('/')}"
    )
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://trakheesi.dubailand.gov.ae",
        "Referer": "https://trakheesi.dubailand.gov.ae/",
        "consumer-id": settings.trakheesi_integration_consumer_id or config.integration_consumer_id,
        "authorizationKey": settings.trakheesi_listing_guid_auth_key or config.listing_guid_auth_key,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    token = (settings.trakheesi_session_token or "").strip()
    if token:
        headers["Token"] = token

    body = {"ListingGUID": guid, "CaptchaToken": captcha}

    async def _call() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0), follow_redirects=True) as client:
            response = await client.post(post_url, json=body, headers=headers)
            if response.status_code >= 400:
                raise ExtractionError(
                    code="madmoun_http_error",
                    message=f"status={response.status_code}",
                    extractor="madmoun",
                    source="trakheesi",
                )
            parsed = response.json()
            if not isinstance(parsed, dict):
                raise ExtractionError(
                    code="madmoun_invalid",
                    message="integration response is not an object",
                    extractor="madmoun",
                    source="trakheesi",
                )
            return parsed

    return await source_concurrency.run("trakheesi", _call)


def integration_to_listing_payload(
    guid: str,
    data: dict[str, Any],
    *,
    url: str | None,
) -> ListingPayload:
    normalized = normalize_integration_body(data)
    broker = MadmounBrokerRecord.model_validate(normalized)
    record = MadmounIntegrationRecord.model_validate(normalized)

    owner_name, owner_phone = extract_owner_fields_from_unknown(normalized)
    license_no = record.license_number or broker.license_number
    txn = record.transaction_number or broker.permit_number

    payload = ListingPayload(
        source="trakheesi",
        permit_number=license_no or txn,
        building=record.building_name_en or record.building_name_ar,
        size_sqft=record.property_size,
        owner_name=owner_name,
        owner_phone=owner_phone,
        raw_payload={
            "trakheesi_integration": {
                "url": url,
                "listing_guid": guid,
                "transaction_number": txn,
                "ad_license": license_no,
                "broker": broker.model_dump(exclude_none=True),
                "api_response": data,
            }
        },
    )
    return strip_broker_owner(payload)