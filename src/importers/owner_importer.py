from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from config import get_settings
from db.enums import ImportRowAction
from db.import_repository import ImportRepository
from db.repository import ListingRepository
from db.session import get_session_factory
from importers.csv_report import build_error_report_csv
from importers.mapping import map_headers, row_to_fields
from importers.matcher import match_listing

log = structlog.get_logger(__name__)


class ImportFileError(ValueError):
    pass


@dataclass(frozen=True)
class ImportResult:
    batch_id: int
    rows_total: int
    rows_inserted: int
    rows_updated: int
    rows_skipped: int
    rows_errored: int
    warnings: list[str]
    error_report_csv: bytes | None = None

    def summary_line(self) -> str:
        return (
            f"Rows: {self.rows_total} | Inserted: {self.rows_inserted} | "
            f"Updated: {self.rows_updated} | Skipped: {self.rows_skipped} | "
            f"Errors: {self.rows_errored}"
        )


def _detect_kind(filename: str, data: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith(".xlsx"):
        return "xlsx"
    if lower.endswith(".xls"):
        return "xls"
    if data[:2] == b"PK":
        return "xlsx"
    if data[:4] == b"\xd0\xcf\x11\xe0":
        return "xls"
    return "csv"


def _read_dataframe(filename: str, data: bytes) -> pd.DataFrame:
    kind = _detect_kind(filename, data)
    if kind == "csv":
        df = pd.read_csv(BytesIO(data), dtype=str, keep_default_na=False)
    elif kind == "xlsx":
        df = pd.read_excel(BytesIO(data), engine="openpyxl")
    else:
        df = pd.read_excel(BytesIO(data), engine="xlrd")
    if df.empty:
        raise ImportFileError("file has no data rows")
    df = df.dropna(how="all")
    if df.empty:
        raise ImportFileError("file has only empty rows")
    return df


def _load_file(file_bytes_or_path: bytes | str | Path, filename: str | None = None) -> tuple[bytes, str]:
    if isinstance(file_bytes_or_path, (str, Path)):
        path = Path(file_bytes_or_path)
        return path.read_bytes(), filename or path.name
    if not isinstance(file_bytes_or_path, (bytes, bytearray)):
        raise TypeError("file_bytes_or_path must be bytes or path")
    if not filename:
        raise ValueError("filename required when passing bytes")
    return bytes(file_bytes_or_path), filename


async def import_owner_file(
    file_bytes_or_path: bytes | str | Path,
    filename: str | None = None,
    *,
    admin_user_id: int,
    mapping_override: dict[str, str] | None = None,
) -> ImportResult:
    data, fname = _load_file(file_bytes_or_path, filename)
    df = await asyncio.to_thread(_read_dataframe, fname, data)
    headers = [str(c) for c in df.columns]
    column_map, warnings = map_headers(headers, override=mapping_override)
    records = df.to_dict(orient="records")

    settings = get_settings()
    factory = get_session_factory()
    rows_inserted = 0
    rows_updated = 0
    rows_skipped = 0
    rows_errored = 0

    async with factory() as session:
        listing_repo = ListingRepository(session, cache_ttl_days=settings.cache_ttl_days)
        import_repo = ImportRepository(session)
        batch = await import_repo.create_batch(
            admin_user_id=admin_user_id,
            filename=fname,
            rows_total=len(records),
            errors=warnings,
        )

        for idx, raw in enumerate(records, start=1):
            raw_row = {k: (None if pd.isna(v) else v) for k, v in raw.items()}
            try:
                fields = row_to_fields(raw_row, column_map)
                if not fields:
                    await import_repo.add_row(
                        batch_id=batch.id,
                        row_index=idx,
                        action=ImportRowAction.SKIPPED,
                        matched_listing_id=None,
                        error="no mappable values",
                        raw_row=raw_row,
                    )
                    rows_skipped += 1
                    continue

                listing = await match_listing(listing_repo, fields)
                updated_listing, action = await listing_repo.upsert_manual_owner(
                    listing,
                    fields,
                    batch_id=batch.id,
                )
                if action == "inserted":
                    rows_inserted += 1
                    row_action = ImportRowAction.INSERTED
                elif action == "updated":
                    rows_updated += 1
                    row_action = ImportRowAction.UPDATED
                else:
                    rows_skipped += 1
                    row_action = ImportRowAction.SKIPPED

                await import_repo.add_row(
                    batch_id=batch.id,
                    row_index=idx,
                    action=row_action,
                    matched_listing_id=updated_listing.id,
                    error=None,
                    raw_row=raw_row,
                )
            except Exception as exc:
                rows_errored += 1
                await import_repo.add_row(
                    batch_id=batch.id,
                    row_index=idx,
                    action=ImportRowAction.ERROR,
                    matched_listing_id=None,
                    error=str(exc),
                    raw_row=raw_row,
                )
                log.warning("import.row_error", row_index=idx, error=str(exc))

        await import_repo.finalize_batch(
            batch,
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            rows_skipped=rows_skipped,
            rows_errored=rows_errored,
            errors=warnings,
        )
        await session.commit()

        error_report: bytes | None = None
        if rows_errored > 0:
            error_rows = await import_repo.error_rows(batch.id)
            error_report = build_error_report_csv(error_rows)

        return ImportResult(
            batch_id=batch.id,
            rows_total=len(records),
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            rows_skipped=rows_skipped,
            rows_errored=rows_errored,
            warnings=warnings,
            error_report_csv=error_report,
        )