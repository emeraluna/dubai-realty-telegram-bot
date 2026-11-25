from functools import lru_cache

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_allowed_ids(value: str) -> list[int]:
    text = value.strip()
    if not text:
        return []
    parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    return [int(p) for p in parts]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    apify_token: str = Field(alias="APIFY_TOKEN")
    scrapeforge_key: str = Field(alias="SCRAPEFORGE_KEY")
    database_url: str = Field(alias="DATABASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    allowed_telegram_ids_env: str = Field(default="", alias="ALLOWED_TELEGRAM_IDS")
    import_admin_ids_env: str = Field(default="", alias="IMPORT_ADMIN_IDS")
    cache_ttl_days: int = Field(default=30, alias="CACHE_TTL_DAYS")
    trakheesi_permit_min_length: int = Field(default=10, alias="TRAKHEESI_PERMIT_MIN_LENGTH")
    trakheesi_permit_max_length: int = Field(default=15, alias="TRAKHEESI_PERMIT_MAX_LENGTH")

    apify_actor_propertyfinder: str = Field(default="", alias="APIFY_ACTOR_PROPERTYFINDER")
    apify_actor_bayut: str = Field(default="", alias="APIFY_ACTOR_BAYUT")
    scrapeforge_base_url: str = Field(default="", alias="SCRAPEFORGE_BASE_URL")
    dld_permit_api_url: str = Field(
        default="https://b2c.dubailand.gov.ae/mv-portal-service/public/permit",
        alias="DLD_PERMIT_API_URL",
    )
    dld_owner_api_urls: str = Field(default="", alias="DLD_OWNER_API_URLS")
    dld_owner_database_enabled: bool = Field(default=True, alias="DLD_OWNER_DATABASE_ENABLED")
    dld_owner_database_url: str = Field(default="", alias="DLD_OWNER_DATABASE_URL")
    dld_owner_table: str = Field(default="property_owners", alias="DLD_OWNER_TABLE")
    dld_owner_col_owner_name: str = Field(default="owner_name", alias="DLD_OWNER_COL_OWNER_NAME")
    dld_owner_col_owner_phone: str = Field(default="owner_phone", alias="DLD_OWNER_COL_OWNER_PHONE")
    dld_owner_col_permit: str = Field(default="permit_number", alias="DLD_OWNER_COL_PERMIT")
    dld_owner_col_ad_license: str = Field(default="ad_license", alias="DLD_OWNER_COL_AD_LICENSE")
    dld_owner_col_transaction: str = Field(default="transaction_number", alias="DLD_OWNER_COL_TRANSACTION")
    dld_owner_col_listing_guid: str = Field(default="listing_guid", alias="DLD_OWNER_COL_LISTING_GUID")
    dld_owner_col_unit: str = Field(default="unit_number", alias="DLD_OWNER_COL_UNIT")
    dld_owner_col_building: str = Field(default="building_name", alias="DLD_OWNER_COL_BUILDING")
    dld_owner_col_plot: str = Field(default="plot_number", alias="DLD_OWNER_COL_PLOT")
    dld_owner_col_pf_id: str = Field(default="pf_listing_id", alias="DLD_OWNER_COL_PF_ID")
    dld_owner_col_real_estate: str = Field(default="real_estate_number", alias="DLD_OWNER_COL_REAL_ESTATE")
    dld_private_owner_urls: str = Field(default="", alias="DLD_PRIVATE_OWNER_URLS")
    dld_jwt_token: str = Field(default="", alias="DLD_JWT_TOKEN")
    dld_api_key: str = Field(default="", alias="DLD_API_KEY")
    dld_subscriber_mobile: str = Field(
        default="",
        alias="DLD_SUBSCRIBER_MOBILE",
        description="DLD-registered mobile used with TRAKHEESI_SESSION_TOKEN / DLD_JWT_TOKEN",
    )
    dld_owner_phone_api_urls: str = Field(default="", alias="DLD_OWNER_PHONE_API_URLS")
    dld_owner_phone_post_urls: str = Field(default="", alias="DLD_OWNER_PHONE_POST_URLS")

    pf_direct_api_urls: str = Field(default="", alias="PF_DIRECT_API_URLS")
    extractor_priority_propertyfinder: str = Field(
        default="propertyfinder_api,apify,scrapeforge,direct",
        alias="EXTRACTOR_PRIORITY_PROPERTYFINDER",
    )
    extractor_priority_bayut: str = Field(
        default="apify,scrapeforge,direct",
        alias="EXTRACTOR_PRIORITY_BAYUT",
    )
    extractor_priority_trakheesi: str = Field(
        default="trakheesi",
        alias="EXTRACTOR_PRIORITY_TRAKHEESI",
    )
    extractor_concurrency_propertyfinder: int = Field(
        default=3,
        alias="EXTRACTOR_CONCURRENCY_PROPERTYFINDER",
    )
    extractor_concurrency_bayut: int = Field(default=3, alias="EXTRACTOR_CONCURRENCY_BAYUT")
    extractor_concurrency_trakheesi: int = Field(default=2, alias="EXTRACTOR_CONCURRENCY_TRAKHEESI")
    import_fuzzy_threshold: int = Field(default=85, alias="IMPORT_FUZZY_THRESHOLD")
    dld_owner_enrichment: bool = Field(default=True, alias="DLD_OWNER_ENRICHMENT")
    dld_try_ad_license: bool = Field(default=True, alias="DLD_TRY_AD_LICENSE")
    dld_ad_license_min_length: int = Field(default=5, alias="DLD_AD_LICENSE_MIN_LENGTH")
    dld_ad_license_max_length: int = Field(default=15, alias="DLD_AD_LICENSE_MAX_LENGTH")
    owner_resolve_enabled: bool = Field(default=True, alias="OWNER_RESOLVE_ENABLED")
    owner_resolve_timeout_hours: float = Field(default=5.0, alias="OWNER_RESOLVE_TIMEOUT_HOURS")
    owner_resolve_poll_seconds: int = Field(default=300, alias="OWNER_RESOLVE_POLL_SECONDS")
    trakheesi_integration_api_base: str = Field(
        default="https://ext.dubailand.gov.ae/trakheesi/",
        alias="TRAKHEESI_INTEGRATION_API_BASE",
    )
    trakheesi_revamp_api_base: str = Field(
        default="https://b2c.dubailand.gov.ae/trakheesi/core/api/",
        alias="TRAKHEESI_REVAMP_API_BASE",
    )
    trakheesi_listing_guid_auth_key: str = Field(default="", alias="TRAKHEESI_LISTING_GUID_AUTH_KEY")
    trakheesi_integration_consumer_id: str = Field(default="", alias="TRAKHEESI_INTEGRATION_CONSUMER_ID")
    trakheesi_session_token: str = Field(
        default="",
        alias="TRAKHEESI_SESSION_TOKEN",
        description="Optional Trakheesi integration Token header (browser cookie ElDEQZ)",
    )
    captcha_api_key: str = Field(default="", alias="CAPTCHA_API_KEY")
    madmoun_playwright_enabled: bool = Field(default=False, alias="MADMOUN_PLAYWRIGHT_ENABLED")
    madmoun_playwright_headless: bool = Field(default=True, alias="MADMOUN_PLAYWRIGHT_HEADLESS")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def allowed_telegram_ids(self) -> list[int]:
        return _parse_allowed_ids(self.allowed_telegram_ids_env)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def import_admin_ids(self) -> list[int]:
        return _parse_allowed_ids(self.import_admin_ids_env)

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> str:
        return str(value or "INFO").upper()


@lru_cache
def get_settings() -> Settings:
    return Settings()