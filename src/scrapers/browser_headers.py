from __future__ import annotations

from config import get_settings


def browser_headers(*, referer: str | None = None, origin: str | None = None) -> dict[str, str]:
    settings = get_settings()
    token = (settings.trakheesi_session_token or "").strip()
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    if referer:
        headers["Referer"] = referer
    if origin:
        headers["Origin"] = origin
    if token:
        headers["Token"] = token
    api_key = (settings.dld_api_key or "").strip()
    if api_key:
        headers["apikey"] = api_key
    jwt = (settings.dld_jwt_token or "").strip()
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    consumer = (settings.trakheesi_integration_consumer_id or "").strip()
    if consumer:
        headers["consumer-id"] = consumer
    auth_key = (settings.trakheesi_listing_guid_auth_key or "").strip()
    if auth_key:
        headers["authorizationKey"] = auth_key
    return headers


def json_api_headers(*, referer: str | None = None) -> dict[str, str]:
    base = browser_headers(referer=referer)
    base["Accept"] = "application/json, text/plain, */*"
    base["Sec-Fetch-Dest"] = "empty"
    base["Sec-Fetch-Mode"] = "cors"
    base["Sec-Fetch-Site"] = "same-origin"
    return base