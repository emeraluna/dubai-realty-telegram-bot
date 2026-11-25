import pytest

from config.settings import Settings


def test_settings_parses_allowed_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("ALLOWED_TELEGRAM_IDS", "111,222,333")
    monkeypatch.setenv("CACHE_TTL_DAYS", "7")

    s = Settings()
    assert s.allowed_telegram_ids == [111, 222, 333]
    assert s.cache_ttl_days == 7


def test_settings_empty_allowed_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setenv("SCRAPEFORGE_KEY", "s")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.delenv("ALLOWED_TELEGRAM_IDS", raising=False)

    s = Settings()
    assert s.allowed_telegram_ids == []