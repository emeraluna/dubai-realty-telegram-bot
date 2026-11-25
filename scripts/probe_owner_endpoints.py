"""Try DLD/Trakheesi endpoints for owner fields (keys from Madmoun integration)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

KEYS = ["32071", "153343", "1106530", "168788844"]
GUID = "qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme"

GETS = [
    "https://b2c.dubailand.gov.ae/mv-portal-service/public/permit/{k}",
    "https://b2c.dubailand.gov.ae/mv-portal-service/private/property/{k}",
    "https://b2c.dubailand.gov.ae/mv-portal-service/private/owner/{k}",
    "https://b2c.dubailand.gov.ae/mv-portal-service/private/property-owner/{k}",
    "https://b2c.dubailand.gov.ae/trakheesi/core/api/public/property/{k}",
    "https://b2c.dubailand.gov.ae/trakheesi/core/api/private/property/{k}",
]

OWNER_MARKERS = ("owner", "landlord", "titledeed", "cardholder")


async def main() -> None:
    from scrapers.trakheesi_runtime import load_trakheesi_public_config

    config = await load_trakheesi_public_config()
    headers = {
        "Accept": "application/json",
        "consumer-id": config.integration_consumer_id,
        "authorizationKey": config.listing_guid_auth_key,
    }
    hits: list[str] = []

    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
        for k in KEYS:
            for tpl in GETS:
                url = tpl.format(k=k)
                try:
                    r = await client.get(url, headers=headers)
                    body = r.text[:4000]
                    low = body.lower()
                    if r.status_code == 200 and any(m in low for m in OWNER_MARKERS):
                        hits.append(f"HIT {r.status_code} {url}\n{body[:800]}\n---")
                    else:
                        print(r.status_code, url, body[:120].replace("\n", " "))
                except Exception as exc:
                    print("ERR", url, exc)

        revamp = (
            f"{config.revamp_api_base.rstrip('/')}/{config.validate_guid_path.lstrip('/')}"
        )
        posts = [
            (revamp, {"ListingGUID": GUID, "authorizationKey": config.listing_guid_auth_key}),
            (
                f"{config.integration_api_base.rstrip('/')}/{config.integration_post_path.lstrip('/')}",
                {"ListingGUID": GUID, "CaptchaToken": ""},
            ),
        ]
        for url, body in posts:
            try:
                r = await client.post(url, json=body, headers=headers)
                text = r.text[:4000]
                low = text.lower()
                if r.status_code == 200:
                    if any(m in low for m in ("ownername", "owner_name", "titledeedowner")):
                        hits.append(f"POST HIT {url}\n{text[:1200]}\n---")
                    else:
                        print("POST", r.status_code, url, text[:200])
                else:
                    print("POST", r.status_code, url, text[:120])
            except Exception as exc:
                print("POST ERR", url, exc)

    if hits:
        out = ROOT / "data" / "owner_probe_hits.json"
        out.write_text(json.dumps(hits, indent=2), encoding="utf-8")
        print("saved", out)
    else:
        print("no owner-bearing endpoints found")


if __name__ == "__main__":
    asyncio.run(main())