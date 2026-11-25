"""Probe integration API with reCAPTCHA anchor (may fail without valid token)."""
import asyncio
import json
import re

import httpx

GUID = "qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme"
SITE_KEY = "6LftQtMrAAAAAMqWWGs3dxfv36VP-5FxOp7c63tl"
AUTH_KEY = "UPA1BTGGKGZAWAGSKYI30B2LO"
CONSUMER = "VBGoCc3mOzdrqb1h3AELe7CBo0XdsIrL"
BASE = "https://ext.dubailand.gov.ae/trakheesi/"
URL = BASE + "j67GCeNsA8/UIBe8OrOcc/FkhqRz6DBs"


async def try_post(captcha: str, token_header: str | None) -> None:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://trakheesi.dubailand.gov.ae",
        "Referer": "https://trakheesi.dubailand.gov.ae/",
        "consumer-id": CONSUMER,
        "authorizationKey": AUTH_KEY,
    }
    if token_header:
        headers["Token"] = token_header
    body = {"ListingGUID": GUID, "CaptchaToken": captcha}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(URL, json=body, headers=headers)
        print("captcha_len", len(captcha), "token", bool(token_header), "status", r.status_code)
        print(r.text[:1500])


async def main() -> None:
    # empty captcha
    await try_post("", None)
    await try_post("", "ElDEQZ")
    # try to get anchor from recaptcha page
    anchor = (
        f"https://www.google.com/recaptcha/api2/anchor?ar=1&k={SITE_KEY}"
        f"&co=aHR0cHM6Ly90cmFraGVlc2kuZHViYWlsYW5kLmdvdi5hZTo0NDM.&hl=en&v=&size=invisible"
    )
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        html = (await client.get(anchor)).text
    m = re.search(r'id="recaptcha-token" value="([^"]+)"', html)
    if m:
        await try_post(m.group(1), None)
        await try_post(m.group(1), "ElDEQZ")
    else:
        print("no anchor token")


asyncio.run(main())