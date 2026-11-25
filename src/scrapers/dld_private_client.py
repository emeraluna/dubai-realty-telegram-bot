from __future__ import annotations

from typing import Any

from config import get_settings
from scrapers.trakheesi_runtime import TrakheesiPublicConfig


def trakheesi_auth_headers(
    config: TrakheesiPublicConfig | None = None,
    *,
    authorization_key: str | None = None,
) -> dict[str, str]:
    settings = get_settings()
    headers: dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://trakheesi.dubailand.gov.ae",
        "Referer": "https://trakheesi.dubailand.gov.ae/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    if config is not None:
        headers["consumer-id"] = settings.trakheesi_integration_consumer_id or config.integration_consumer_id
        key = authorization_key or settings.trakheesi_listing_guid_auth_key or config.listing_guid_auth_key
        if key:
            headers["authorizationKey"] = key
    else:
        if settings.trakheesi_integration_consumer_id:
            headers["consumer-id"] = settings.trakheesi_integration_consumer_id
        if settings.trakheesi_listing_guid_auth_key:
            headers["authorizationKey"] = settings.trakheesi_listing_guid_auth_key

    session_token = (settings.trakheesi_session_token or "").strip()
    if session_token:
        headers["Token"] = session_token
    jwt = (settings.dld_jwt_token or "").strip()
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    api_key = (settings.dld_api_key or "").strip()
    if api_key:
        headers["X-API-KEY"] = api_key
    return headers


def merge_post_body(base: dict[str, Any], config: TrakheesiPublicConfig | None) -> dict[str, Any]:
    settings = get_settings()
    body = dict(base)
    key = settings.trakheesi_listing_guid_auth_key
    if config and not key:
        key = config.listing_guid_auth_key
    if key and "authorizationKey" not in body:
        body["authorizationKey"] = key
    return body