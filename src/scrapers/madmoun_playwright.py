from __future__ import annotations

import json
from typing import Any

from config import get_settings
from scrapers.errors import ExtractionError

_INTEGRATION_PATH = "FkhqRz6DBs"


async def fetch_madmoun_integration_json(url: str, *, timeout_ms: int = 90_000) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise ExtractionError(
            code="madmoun_playwright_missing",
            message="playwright is not installed",
            extractor="madmoun",
            source="trakheesi",
        ) from exc

    captured: dict[str, Any] | None = None

    def _is_integration(response: Any) -> bool:
        return _INTEGRATION_PATH in response.url and response.status >= 200 and response.status < 300

    settings = get_settings()
    async with async_playwright() as playwright:
        launch_kwargs: dict[str, Any] = {"headless": settings.madmoun_playwright_headless}
        try:
            browser = await playwright.chromium.launch(channel="msedge", **launch_kwargs)
        except Exception:
            browser = await playwright.chromium.launch(**launch_kwargs)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            view_details = page.locator("button").filter(has_text="View Details")
            if await view_details.count() > 0:
                target = view_details.first
                try:
                    async with page.expect_response(_is_integration, timeout=timeout_ms) as response_info:
                        await target.click(force=True, timeout=min(timeout_ms, 45_000))
                    response = await response_info.value
                    body = await response.json()
                    if isinstance(body, dict):
                        captured = body
                except Exception:
                    try:
                        await target.click(force=True, timeout=15_000)
                        await page.wait_for_timeout(8000)
                    except Exception:
                        pass
            if captured is None:
                text = await page.evaluate("document.body.innerText")
                if "authorization failed" in text.lower():
                    raise ExtractionError(
                        code="madmoun_auth_failed",
                        message="trakheesi rejected headless validation (set TRAKHEESI_SESSION_TOKEN or CAPTCHA_API_KEY)",
                        extractor="madmoun",
                        source="trakheesi",
                    )
                if "verified by Dubai Land Department" in text:
                    captured = {"result": {"_visible_text": text}}
        finally:
            await browser.close()

    if not captured:
        raise ExtractionError(
            code="madmoun_playwright_empty",
            message="no integration API response captured",
            extractor="madmoun",
            source="trakheesi",
        )
    return captured