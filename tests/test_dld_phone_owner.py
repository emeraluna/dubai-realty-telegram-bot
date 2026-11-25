import pytest
import respx

from scrapers.dld_phone_owner import fetch_dld_owner_by_phone


@pytest.mark.asyncio
@respx.mock
async def test_dld_phone_get_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv(
        "DLD_OWNER_PHONE_API_URLS",
        "https://b2c.dubailand.gov.ae/mv-portal-service/private/owner/mobile/{phone}",
    )
    monkeypatch.setenv("DLD_OWNER_PHONE_POST_URLS", "-")
    monkeypatch.setenv("TRAKHEESI_INTEGRATION_CONSUMER_ID", "test-consumer")
    monkeypatch.setenv("TRAKHEESI_LISTING_GUID_AUTH_KEY", "test-auth")

    async def _config():
        from scrapers.trakheesi_runtime import TrakheesiPublicConfig

        return TrakheesiPublicConfig(
            integration_api_base="https://ext.dubailand.gov.ae/trakheesi/",
            integration_post_path="x",
            listing_guid_auth_key="test-auth",
            integration_consumer_id="test-consumer",
            validate_guid_path="y",
            revamp_api_base="https://b2c.dubailand.gov.ae/trakheesi/core/api/",
        )

    monkeypatch.setattr("scrapers.dld_phone_owner.load_trakheesi_public_config", _config)
    respx.get(
        "https://b2c.dubailand.gov.ae/mv-portal-service/private/owner/mobile/971521149496"
    ).respond(
        json={"ownerName": "DLD Owner", "ownerPhone": "+971521149496", "licenseNumber": "1106530"}
    )
    from config.settings import get_settings

    get_settings.cache_clear()
    payload = await fetch_dld_owner_by_phone("+971521149496")
    assert payload.owner_name == "DLD Owner"
    assert payload.permit_number == "1106530"