"""Create projects, pieces, nodes, and steps.

Revision ID: 0001
Revises:
Create Date: 2026-11-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

node_kind = sa.Enum("generated", "uploaded", name="nodekind", native_enum=False, length=32)
node_status = sa.Enum(
	"generating", "finished", "stopped", "failed", name="nodestatus", native_enum=False, length=32
)


def upgrade() -> None:
	"""Create the four tables that hold a project's work."""
	op.create_table(
		"projects",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("name", sa.Text(), nullable=False),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
		sa.PrimaryKeyConstraint("id"),
	)

	op.create_table(
		"pieces",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("project_id", sa.Uuid(), nullable=False),
		sa.Column("name", sa.Text(), nullable=False),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
		sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
		sa.PrimaryKeyConstraint("id"),
	)
	op.create_index("ix_pieces_project_id", "pieces", ["project_id"])

	# Leave out the link to steps for now, because that table does not exist yet.
	op.create_table(
		"nodes",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("piece_id", sa.Uuid(), nullable=False),
		sa.Column("parent_node_id", sa.Uuid(), nullable=True),
		sa.Column("parent_step_id", sa.Uuid(), nullable=True),
		sa.Column("kind", node_kind, nullable=False),
		sa.Column("status", node_status, nullable=False),
		sa.Column("prompt", sa.Text(), nullable=False),
		sa.Column("model", sa.Text(), nullable=True),
		sa.Column("is_step_by_step", sa.Boolean(), nullable=False),
		sa.Column("parameter_values", sa.JSON(), nullable=False),
		sa.Column("failure_message", sa.Text(), nullable=True),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
		sa.ForeignKeyConstraint(["piece_id"], ["pieces.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["parent_node_id"], ["nodes.id"], ondelete="SET NULL"),
		sa.PrimaryKeyConstraint("id"),
	)
	op.create_index("ix_nodes_piece_id", "nodes", ["piece_id"])
	op.create_index("ix_nodes_parent_node_id", "nodes", ["parent_node_id"])

	op.create_table(
		"steps",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("node_id", sa.Uuid(), nullable=False),
		sa.Column("step_index", sa.Integer(), nullable=False),
		sa.Column("source", sa.Text(), nullable=False),
		sa.Column("step_reasoning", sa.Text(), nullable=False),
		sa.Column("render_svg", sa.Text(), nullable=False),
		sa.Column("is_rejected", sa.Boolean(), nullable=False),
		sa.Column("rejection_reason", sa.Text(), nullable=True),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
		sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
		sa.PrimaryKeyConstraint("id"),
		sa.UniqueConstraint("node_id", "step_index", name="uq_steps_node_id_step_index"),
	)
	op.create_index("ix_steps_node_id", "steps", ["node_id"])

	# Link a node to the step it starts from, now that both tables exist.
	with op.batch_alter_table("nodes") as batch_op:
		batch_op.create_foreign_key(
			"fk_nodes_parent_step_id", "steps", ["parent_step_id"], ["id"], ondelete="SET NULL"
		)


def downgrade() -> None:
	"""Drop the four tables."""
	with op.batch_alter_table("nodes") as batch_op:
		batch_op.drop_constraint("fk_nodes_parent_step_id", type_="foreignkey")

	op.drop_table("steps")
	op.drop_table("nodes")
	op.drop_table("pieces")
	op.drop_table("projects")
