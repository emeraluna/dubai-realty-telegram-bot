"""listings and lookups tables

Revision ID: 20241124_0001
Revises:
Create Date: 2024-11-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20241124_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_listing_id", sa.String(length=128), nullable=True),
        sa.Column("unit_number", sa.String(length=64), nullable=True),
        sa.Column("floor", sa.String(length=64), nullable=True),
        sa.Column("building", sa.String(length=256), nullable=True),
        sa.Column("community", sa.String(length=256), nullable=True),
        sa.Column("developer", sa.String(length=256), nullable=True),
        sa.Column("size_sqft", sa.Float(), nullable=True),
        sa.Column("plot_number", sa.String(length=128), nullable=True),
        sa.Column("permit_number", sa.String(length=128), nullable=True),
        sa.Column("permit_status", sa.String(length=128), nullable=True),
        sa.Column("owner_name", sa.String(length=256), nullable=True),
        sa.Column("owner_phone", sa.String(length=64), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("lookup_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_listing_id", name="uq_listings_source_listing"),
    )
    op.create_index("ix_listings_last_seen_at", "listings", ["last_seen_at"], unique=False)
    op.create_index("ix_listings_permit_number", "listings", ["permit_number"], unique=False)

    op.create_table(
        "lookups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("requested_input", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cache_hit", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lookups_listing_id", "lookups", ["listing_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lookups_listing_id", table_name="lookups")
    op.drop_table("lookups")
    op.drop_index("ix_listings_permit_number", table_name="listings")
    op.drop_index("ix_listings_last_seen_at", table_name="listings")
    op.drop_table("listings")