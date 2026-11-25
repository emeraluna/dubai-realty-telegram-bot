from __future__ import annotations

import asyncio
from typing import Any

import httpx

from config import get_settings

_TRAKHEESI_SITE_KEY = "6LftQtMrAAAAAMqWWGs3dxfv36VP-5FxOp7c63tl"
_LISTING_VALIDATION_ACTION = "listing_validation"
_VALIDATION_PAGE = "https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation"


async def _solve_via_2captcha(api_key: str, page_url: str) -> str:
    create_payload = {
        "key": api_key,
        "method": "userrecaptcha",
        "googlekey": _TRAKHEESI_SITE_KEY,
        "pageurl": page_url,
        "version": "v3",
        "action": _LISTING_VALIDATION_ACTION,
        "min_score": 0.3,
        "json": 1,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        create = await client.post("https://2captcha.com/in.php", data=create_payload)
        create.raise_for_status()
        body: dict[str, Any] = create.json()
        if body.get("status") != 1:
            raise RuntimeError(f"2captcha create failed: {body}")
        request_id = str(body["request"])

        for _ in range(40):
            await asyncio.sleep(5)
            poll = await client.get(
                "https://2captcha.com/res.php",
                params={"key": api_key, "action": "get", "id": request_id, "json": 1},
            )
            poll.raise_for_status()
            result: dict[str, Any] = poll.json()
            if result.get("status") == 1:
                token = result.get("request")
                if isinstance(token, str) and token:
                    return token
            if result.get("request") != "CAPCHA_NOT_READY":
                raise RuntimeError(f"2captcha poll failed: {result}")
        raise TimeoutError("2captcha timeout")


async def fetch_listing_validation_captcha(page_url: str | None = None) -> str | None:
    settings = get_settings()
    api_key = (settings.captcha_api_key or "").strip()
    if not api_key:
        return None
    url = page_url or _VALIDATION_PAGE
    return await _solve_via_2captcha(api_key, url)