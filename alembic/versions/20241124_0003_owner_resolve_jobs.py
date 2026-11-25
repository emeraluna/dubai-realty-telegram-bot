"""owner resolve jobs

Revision ID: 20241124_0003
Revises: 20241124_0002
Create Date: 2024-11-25 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20241124_0003"
down_revision: Union[str, Sequence[str], None] = "20241124_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

owner_resolve_status = sa.Enum(
    "pending",
    "running",
    "succeeded",
    "failed",
    name="owner_resolve_status",
    native_enum=False,
)


def upgrade() -> None:
    owner_resolve_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "owner_resolve_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("requested_input", sa.Text(), nullable=False),
        sa.Column(
            "status",
            owner_resolve_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("notify_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("notify_message_id", sa.BigInteger(), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_owner_resolve_jobs_status", "owner_resolve_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_owner_resolve_jobs_status", table_name="owner_resolve_jobs")
    op.drop_table("owner_resolve_jobs")
    owner_resolve_status.drop(op.get_bind(), checkfirst=True)