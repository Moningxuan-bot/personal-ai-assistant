"""add memory contradiction fields

Revision ID: c4a8d1e2b002
Revises: b3f2c8d9a101
Create Date: 2026-06-16 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c4a8d1e2b002"
down_revision: Union[str, None] = "b3f2c8d9a101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "memories",
        sa.Column("contradiction_topic", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "memories",
        sa.Column("contradiction_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "memories",
        sa.Column("contradiction_history", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        op.f("ix_memories_contradiction_topic"),
        "memories",
        ["contradiction_topic"],
        unique=False,
    )
    op.alter_column("memories", "contradiction_count", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_memories_contradiction_topic"), table_name="memories")
    op.drop_column("memories", "contradiction_history")
    op.drop_column("memories", "contradiction_count")
    op.drop_column("memories", "contradiction_topic")
