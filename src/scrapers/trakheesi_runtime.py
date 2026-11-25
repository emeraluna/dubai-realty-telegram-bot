from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import parse_qs, urlparse

import httpx

_TRAKHEESI_JS = "https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js"


@dataclass(frozen=True)
class TrakheesiPublicConfig:
    integration_api_base: str
    integration_post_path: str
    listing_guid_auth_key: str
    integration_consumer_id: str
    validate_guid_path: str
    revamp_api_base: str


def _extract(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def _parse_trakheesi_bundle(text: str) -> TrakheesiPublicConfig:
    integration_base = _extract(
        r'trakheesi_integration_api_endpoint:"([^"]+)"',
        text,
    )
    revamp_base = _extract(r'trakheesi_revamp_api_endpoint:"([^"]+)"', text)
    auth_key = _extract(
        r'(?:REACT_APP_)?listing_guid_validation_authorization_key:"([^"]+)"',
        text,
    )
    consumer = _extract(
        r'(?:REACT_APP_)?trakheesi_api_integration_consumer_id:"([^"]+)"',
        text,
    )
    if not consumer:
        consumer = _extract(
            r'(?:REACT_APP_)?trakheesi_integration_api_consumer_id:"([^"]+)"',
            text,
        )
    post_path = _extract(
        r'trakheesi_integration_api_endpoint,"([^"]+)"\)',
        text,
    )
    if not post_path:
        post_path = "j67GCeNsA8/UIBe8OrOcc/FkhqRz6DBs"
    validate_guid = _extract(
        r'validateListingDetailsUsingGuid1:"([^"]+)"',
        text,
    )
    if not integration_base or not auth_key or not consumer or not validate_guid:
        raise ValueError("trakheesi bundle missing required public config fields")
    if not revamp_base:
        revamp_base = "https://b2c.dubailand.gov.ae/trakheesi/core/api/"
    return TrakheesiPublicConfig(
        integration_api_base=integration_base,
        integration_post_path=post_path,
        listing_guid_auth_key=auth_key,
        integration_consumer_id=consumer,
        validate_guid_path=validate_guid,
        revamp_api_base=revamp_base,
    )


@lru_cache(maxsize=1)
def _cached_bundle_text() -> str:
    with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
        response = client.get(_TRAKHEESI_JS)
        response.raise_for_status()
        return response.text


async def load_trakheesi_public_config() -> TrakheesiPublicConfig:
    text = await asyncio.to_thread(_cached_bundle_text)
    return _parse_trakheesi_bundle(text)


def parse_listing_guid_from_validation_url(url: str) -> str | None:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ("khevJujtDig", "listingGuid", "listingGUID"):
        if key in qs and qs[key]:
            return qs[key][0]
    return None