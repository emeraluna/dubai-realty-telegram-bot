"""Fetch Madmoun integration JSON using public Trakheesi keys + 2captcha if set."""
from __future__ import annotations

import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "t")
os.environ.setdefault("APIFY_TOKEN", "a")
os.environ.setdefault("SCRAPEFORGE_KEY", "s")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///data/realty.db")

GUID = "qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme"
URL = (
    "https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation"
    f"?khevJujtDig={GUID}"
)

from config.settings import get_settings  # noqa: E402

get_settings.cache_clear()

from scrapers.trakheesi_recaptcha import fetch_listing_validation_captcha  # noqa: E402
from scrapers.trakheesi_runtime import load_trakheesi_public_config  # noqa: E402
from scrapers.madmoun_validation import _fetch_by_listing_guid  # noqa: E402
from scrapers.dld_owner_api import fetch_dld_owner_by_key  # noqa: E402
from services.permit_candidates import extract_owner_fields_from_unknown  # noqa: E402

import httpx  # noqa: E402


async def integration_raw() -> dict:
    config = await load_trakheesi_public_config()
    captcha = await fetch_listing_validation_captcha(URL)
    if not captcha:
        raise RuntimeError("CAPTCHA_API_KEY not set — cannot call integration API headlessly")
    base = config.integration_api_base.rstrip("/")
    post = f"{base}/{config.integration_post_path.lstrip('/')}"
    headers = {
        "Content-Type": "application/json",
        "consumer-id": config.integration_consumer_id,
        "authorizationKey": config.listing_guid_auth_key,
        "Origin": "https://trakheesi.dubailand.gov.ae",
        "Referer": "https://trakheesi.dubailand.gov.ae/",
    }
    token = (get_settings().trakheesi_session_token or "").strip()
    if token:
        headers["Token"] = token
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            post,
            json={"ListingGUID": GUID, "CaptchaToken": captcha},
            headers=headers,
        )
        r.raise_for_status()
        return r.json()


async def main() -> None:
    try:
        data = await integration_raw()
    except Exception as exc:
        print("integration", exc)
        data = await _fetch_by_listing_guid(GUID, validation_url=URL)
    print("integration_json", json.dumps(data, ensure_ascii=False)[:8000])
    inner = data.get("Response") or data.get("result") or data
    owner_name, owner_phone = extract_owner_fields_from_unknown(inner)
    print("extracted_owner", owner_name, owner_phone)
    for key in ("153343", "1106530", GUID):
        try:
            p = await fetch_dld_owner_by_key(key)
            print("dld_owner", key, p.owner_name, p.owner_phone)
        except Exception as e:
            print("dld_owner", key, type(e).__name__)


asyncio.run(main())