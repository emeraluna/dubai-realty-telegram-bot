from __future__ import annotations

import pytest
import respx
from httpx import Response

from scrapers.dld_private_owner import fetch_dld_private_owner_by_key


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dld_private_owner_by_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv(
        "DLD_PRIVATE_OWNER_URLS",
        "https://b2c.dubailand.gov.ae/mv-portal-service/private/owner/{key}",
    )
    monkeypatch.setenv("TRAKHEESI_INTEGRATION_CONSUMER_ID", "test-consumer")
    monkeypatch.setenv("TRAKHEESI_LISTING_GUID_AUTH_KEY", "test-auth")
    from config.settings import get_settings

    get_settings.cache_clear()

    respx.get("https://b2c.dubailand.gov.ae/mv-portal-service/private/owner/32071").mock(
        return_value=Response(200, json={"ownerName": "Private Owner", "ownerPhone": "+971501111111"})
    )
    payload = await fetch_dld_private_owner_by_key("32071")
    assert payload.owner_name == "Private Owner"
    assert payload.owner_phone == "+971501111111"