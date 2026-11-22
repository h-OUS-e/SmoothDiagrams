"""Add exports, which remember every download of a node.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

export_format = sa.Enum(
	"svelte", "svg", "png", "jpeg", name="exportformat", native_enum=False, length=32
)


def upgrade() -> None:
	"""Create the table of exports."""
	op.create_table(
		"exports",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("node_id", sa.Uuid(), nullable=False),
		sa.Column("step_id", sa.Uuid(), nullable=True),
		sa.Column("format", export_format, nullable=False),
		sa.Column("parameter_values", sa.JSON(), nullable=False),
		sa.Column("animation_time", sa.Float(), nullable=False),
		sa.Column("pixel_width", sa.Integer(), nullable=True),
		sa.Column("pixel_height", sa.Integer(), nullable=True),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
		sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["step_id"], ["steps.id"], ondelete="SET NULL"),
		sa.PrimaryKeyConstraint("id"),
	)
	op.create_index("ix_exports_node_id", "exports", ["node_id"])


def downgrade() -> None:
	"""Drop the table of exports."""
	op.drop_index("ix_exports_node_id", table_name="exports")
	op.drop_table("exports")
