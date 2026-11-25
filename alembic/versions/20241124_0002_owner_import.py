"""owner import schema

Revision ID: 20241124_0002
Revises: 20241124_0001
Create Date: 2024-11-24 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20241124_0002"
down_revision: Union[str, Sequence[str], None] = "20241124_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

owner_source = sa.Enum("scraped", "manual", "unknown", name="owner_source", native_enum=False)
import_row_action = sa.Enum(
    "inserted",
    "updated",
    "skipped",
    "error",
    name="import_row_action",
    native_enum=False,
)


def upgrade() -> None:
    owner_source.create(op.get_bind(), checkfirst=True)
    import_row_action.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "listings",
        sa.Column(
            "owner_source",
            owner_source,
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "listings",
        sa.Column("owner_updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        UPDATE listings
        SET owner_source = 'scraped'
        WHERE (owner_name IS NOT NULL AND TRIM(owner_name) <> '')
           OR (owner_phone IS NOT NULL AND TRIM(owner_phone) <> '')
        """
    )

    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admin_user_id", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("rows_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_errored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_batches_created_at", "import_batches", ["created_at"], unique=False)

    op.create_table(
        "import_rows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("action", import_row_action, nullable=False),
        sa.Column("matched_listing_id", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("raw_row", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_listing_id"], ["listings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_rows_batch_id", "import_rows", ["batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_rows_batch_id", table_name="import_rows")
    op.drop_table("import_rows")
    op.drop_index("ix_import_batches_created_at", table_name="import_batches")
    op.drop_table("import_batches")
    op.drop_column("listings", "owner_updated_at")
    op.drop_column("listings", "owner_source")
    import_row_action.drop(op.get_bind(), checkfirst=True)
    owner_source.drop(op.get_bind(), checkfirst=True)