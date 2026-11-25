from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from config import get_settings
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload

log = structlog.get_logger(__name__)


@lru_cache
def _owner_engine() -> AsyncEngine | None:
    settings = get_settings()
    url = (settings.dld_owner_database_url or "").strip()
    if not url:
        return None
    return create_async_engine(url, pool_pre_ping=True)


def _session_factory() -> async_sessionmaker[AsyncSession] | None:
    engine = _owner_engine()
    if engine is None:
        return None
    return async_sessionmaker(engine, expire_on_commit=False)


def _lookup_keys(listing_fields: dict[str, Any]) -> list[tuple[str, str]]:
    settings = get_settings()
    keys: list[tuple[str, str]] = []
    mapping = {
        settings.dld_owner_col_permit: listing_fields.get("permit_number"),
        settings.dld_owner_col_ad_license: listing_fields.get("permit_number"),
        settings.dld_owner_col_transaction: listing_fields.get("transaction_number"),
        settings.dld_owner_col_listing_guid: listing_fields.get("listing_guid"),
        settings.dld_owner_col_unit: listing_fields.get("unit_number"),
        settings.dld_owner_col_building: listing_fields.get("building"),
        settings.dld_owner_col_plot: listing_fields.get("plot_number"),
        settings.dld_owner_col_pf_id: listing_fields.get("source_listing_id"),
        settings.dld_owner_col_real_estate: listing_fields.get("real_estate_number"),
    }
    for column, value in mapping.items():
        if not column or value is None:
            continue
        text_val = str(value).strip()
        if text_val:
            keys.append((column, text_val))
    return keys


async def fetch_owner_from_dld_database(listing_fields: dict[str, Any]) -> ListingPayload:
    settings = get_settings()
    if not settings.dld_owner_database_enabled:
        raise ExtractionError(
            code="dld_db_disabled",
            message="DLD owner database lookup disabled",
            extractor="dld_db",
            source="dld",
        )

    factory = _session_factory()
    if factory is None:
        raise ExtractionError(
            code="dld_db_not_configured",
            message="DLD_OWNER_DATABASE_URL missing",
            extractor="dld_db",
            source="dld",
        )

    table = settings.dld_owner_table.strip()
    name_col = settings.dld_owner_col_owner_name.strip()
    phone_col = settings.dld_owner_col_owner_phone.strip()
    if not table or not name_col or not phone_col:
        raise ExtractionError(
            code="dld_db_schema",
            message="owner table/column settings incomplete",
            extractor="dld_db",
            source="dld",
        )

    candidates = _lookup_keys(listing_fields)
    if not candidates:
        raise ExtractionError(
            code="dld_db_no_keys",
            message="no lookup keys for DLD owner database",
            extractor="dld_db",
            source="dld",
        )

    sql_parts = [
        f"SELECT {name_col} AS owner_name, {phone_col} AS owner_phone",
        f"FROM {table}",
        "WHERE",
    ]
    binds: dict[str, Any] = {}
    wheres: list[str] = []
    for idx, (column, value) in enumerate(candidates):
        key = f"v{idx}"
        wheres.append(f"{column} = :{key}")
        binds[key] = value
    sql_parts.append(" OR ".join(wheres))
    sql_parts.append("LIMIT 1")
    statement = text(" ".join(sql_parts))

    async with factory() as session:
        result = await session.execute(statement, binds)
        row = result.mappings().first()

    if not row:
        raise ExtractionError(
            code="dld_db_not_found",
            message="owner row not found",
            extractor="dld_db",
            source="dld",
        )

    owner_name = row.get("owner_name")
    owner_phone = row.get("owner_phone")
    for val in (owner_name, owner_phone):
        if isinstance(val, str) and val.strip().upper().startswith("REPLACE_WITH"):
            raise ExtractionError(
                code="dld_db_placeholder",
                message="owner row contains seed placeholder",
                extractor="dld_db",
                source="dld",
            )
    if not owner_name and not owner_phone:
        raise ExtractionError(
            code="dld_db_empty_owner",
            message="owner row has no contact fields",
            extractor="dld_db",
            source="dld",
        )

    log.info(
        "dld_owner_database.hit",
        table=table,
        keys=[c[0] for c in candidates],
    )
    return ListingPayload(
        source="dld",
        owner_name=str(owner_name).strip() if owner_name else None,
        owner_phone=str(owner_phone).strip() if owner_phone else None,
        raw_payload={"dld_owner_database": {"table": table, "binds": binds}},
    )


async def fetch_owner_from_dld_database_by_phone(phone: str) -> ListingPayload:
    from services.uae_phone import uae_phone_variants

    settings = get_settings()
    if not settings.dld_owner_database_enabled:
        raise ExtractionError(
            code="dld_db_disabled",
            message="DLD owner database lookup disabled",
            extractor="dld_db",
            source="dld",
        )

    factory = _session_factory()
    if factory is None:
        raise ExtractionError(
            code="dld_db_not_configured",
            message="DLD_OWNER_DATABASE_URL missing",
            extractor="dld_db",
            source="dld",
        )

    table = settings.dld_owner_table.strip()
    name_col = settings.dld_owner_col_owner_name.strip()
    phone_col = settings.dld_owner_col_owner_phone.strip()
    variants = uae_phone_variants(phone)
    if not variants:
        raise ExtractionError(
            code="dld_db_no_phone",
            message="empty phone",
            extractor="dld_db",
            source="dld",
        )

    binds: dict[str, Any] = {}
    wheres: list[str] = []
    for idx, variant in enumerate(variants):
        key = f"p{idx}"
        binds[key] = variant
        wheres.append(f"{phone_col} = :{key}")
    statement = text(
        f"SELECT {name_col} AS owner_name, {phone_col} AS owner_phone, "
        f"{settings.dld_owner_col_ad_license} AS ad_license, "
        f"{settings.dld_owner_col_building} AS building_name "
        f"FROM {table} WHERE " + " OR ".join(wheres) + " LIMIT 1"
    )

    async with factory() as session:
        result = await session.execute(statement, binds)
        row = result.mappings().first()

    if not row:
        raise ExtractionError(
            code="dld_db_not_found",
            message="owner row not found for phone",
            extractor="dld_db",
            source="dld",
        )

    owner_name = row.get("owner_name")
    owner_phone = row.get("owner_phone")
    if not owner_name and not owner_phone:
        raise ExtractionError(
            code="dld_db_empty_owner",
            message="owner row has no contact fields",
            extractor="dld_db",
            source="dld",
        )

    return ListingPayload(
        source="dld",
        owner_name=str(owner_name).strip() if owner_name else None,
        owner_phone=str(owner_phone).strip() if owner_phone else None,
        permit_number=str(row["ad_license"]).strip() if row.get("ad_license") else None,
        building=str(row["building_name"]).strip() if row.get("building_name") else None,
        raw_payload={"dld_owner_database": {"mode": "phone", "variants": variants}},
    )