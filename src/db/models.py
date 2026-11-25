from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from db.base import Base
from db.enums import ImportRowAction, OwnerResolveStatus, OwnerSource


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("source", "source_listing_id", name="uq_listings_source_listing"),
        Index("ix_listings_permit_number", "permit_number"),
        Index("ix_listings_last_seen_at", "last_seen_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_listing_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    floor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    building: Mapped[str | None] = mapped_column(String(256), nullable=True)
    community: Mapped[str | None] = mapped_column(String(256), nullable=True)
    developer: Mapped[str | None] = mapped_column(String(256), nullable=True)
    size_sqft: Mapped[float | None] = mapped_column(nullable=True)
    plot_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    permit_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    permit_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    owner_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_source: Mapped[str] = mapped_column(
        Enum(OwnerSource, values_callable=lambda x: [e.value for e in x], native_enum=False),
        nullable=False,
        default=OwnerSource.UNKNOWN.value,
        server_default=OwnerSource.UNKNOWN.value,
    )
    owner_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    lookup_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    lookups: Mapped[list[Lookup]] = relationship(back_populates="listing", lazy="selectin")
    import_rows: Mapped[list["ImportRow"]] = relationship(back_populates="listing", lazy="selectin")


class Lookup(Base):
    __tablename__ = "lookups"
    __table_args__ = (Index("ix_lookups_listing_id", "listing_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requested_input: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    listing: Mapped[Listing] = relationship(back_populates="lookups")


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (Index("ix_import_batches_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    rows_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rows_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rows_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rows_errored: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    errors: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    rows: Mapped[list["ImportRow"]] = relationship(back_populates="batch", lazy="selectin")


class ImportRow(Base):
    __tablename__ = "import_rows"
    __table_args__ = (Index("ix_import_rows_batch_id", "batch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(
        Enum(ImportRowAction, values_callable=lambda x: [e.value for e in x], native_enum=False),
        nullable=False,
    )
    matched_listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("listings.id", ondelete="SET NULL"),
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_row: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )

    batch: Mapped[ImportBatch] = relationship(back_populates="rows")
    listing: Mapped[Listing | None] = relationship(back_populates="import_rows")


class OwnerResolveJob(Base):
    __tablename__ = "owner_resolve_jobs"
    __table_args__ = (Index("ix_owner_resolve_jobs_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    requested_input: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(OwnerResolveStatus, values_callable=lambda x: [e.value for e in x], native_enum=False),
        nullable=False,
        default=OwnerResolveStatus.PENDING.value,
        server_default=OwnerResolveStatus.PENDING.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    notify_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    notify_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    listing: Mapped[Listing] = relationship(lazy="selectin")