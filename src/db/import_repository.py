from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.enums import ImportRowAction
from db.models import ImportBatch, ImportRow


class ImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_batch(
        self,
        *,
        admin_user_id: int,
        filename: str,
        rows_total: int,
        errors: list[Any] | None = None,
    ) -> ImportBatch:
        batch = ImportBatch(
            admin_user_id=admin_user_id,
            filename=filename,
            rows_total=rows_total,
            errors=errors or [],
        )
        self._session.add(batch)
        await self._session.flush()
        return batch

    async def finalize_batch(
        self,
        batch: ImportBatch,
        *,
        rows_inserted: int,
        rows_updated: int,
        rows_skipped: int,
        rows_errored: int,
        errors: list[Any] | None = None,
    ) -> ImportBatch:
        batch.rows_inserted = rows_inserted
        batch.rows_updated = rows_updated
        batch.rows_skipped = rows_skipped
        batch.rows_errored = rows_errored
        if errors is not None:
            batch.errors = errors
        await self._session.flush()
        return batch

    async def add_row(
        self,
        *,
        batch_id: int,
        row_index: int,
        action: ImportRowAction | str,
        matched_listing_id: int | None,
        error: str | None,
        raw_row: dict[str, Any],
    ) -> ImportRow:
        row = ImportRow(
            batch_id=batch_id,
            row_index=row_index,
            action=str(action),
            matched_listing_id=matched_listing_id,
            error=error,
            raw_row=raw_row,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_batch(self, batch_id: int) -> ImportBatch | None:
        stmt = select(ImportBatch).where(ImportBatch.id == batch_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def recent_batches(self, *, limit: int = 10) -> list[ImportBatch]:
        stmt = select(ImportBatch).order_by(ImportBatch.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def error_rows(self, batch_id: int) -> list[ImportRow]:
        stmt = (
            select(ImportRow)
            .where(ImportRow.batch_id == batch_id)
            .where(ImportRow.action == ImportRowAction.ERROR.value)
            .order_by(ImportRow.row_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())