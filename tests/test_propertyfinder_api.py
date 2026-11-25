import json

import httpx
import pytest
import respx

from scrapers.propertyfinder_api import fetch_propertyfinder_listing
from services.lookup_request import LookupRequest


@pytest.mark.asyncio
@respx.mock
async def test_propertyfinder_api_json_owner() -> None:
    body = {
        "listing": {
            "id": "168788844",
            "ownerName": "Registry Owner",
            "ownerPhone": "+971501112233",
            "rera": {"issued_license_number": "1106530"},
        }
    }
    respx.get("https://www.propertyfinder.ae/api/pwa/property/168788844").respond(
        json=body,
        headers={"content-type": "application/json"},
    )
    req = LookupRequest(
        source="propertyfinder",
        external_id="168788844",
        raw_input="https://www.propertyfinder.ae/en/plp/buy/apartment-168788844.html",
    )
    payload = await fetch_propertyfinder_listing(req)
    assert payload.owner_name == "Registry Owner"
    assert payload.owner_phone == "+971501112233"
    assert payload.permit_number == "1106530"


@pytest.mark.asyncio
@respx.mock
async def test_propertyfinder_api_embedded_html_fallback() -> None:
    html = (
        '<html><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(
            {
                "props": {
                    "pageProps": {
                        "listing": {"landlordName": "HTML Owner", "landlordPhone": "+971509990000"}
                    }
                }
            }
        )
        + "</script></html>"
    )
    respx.get(url__regex=r"https://www\.propertyfinder\.ae/.*168788844").respond(
        text=html,
        headers={"content-type": "text/html"},
    )
    req = LookupRequest(
        source="propertyfinder",
        external_id="168788844",
        raw_input="https://www.propertyfinder.ae/en/plp/buy/apartment-168788844.html",
    )
    payload = await fetch_propertyfinder_listing(req)
    assert payload.owner_name == "HTML Owner"
    assert payload.owner_phone == "+971509990000"