"""Add interface versions, and move taste prior switches into them.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
	"""Create interface versions and point projects and nodes at them."""
	op.create_table(
		"interface_versions",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("project_id", sa.Uuid(), nullable=False),
		sa.Column("version_number", sa.Integer(), nullable=False),
		sa.Column("settings", sa.JSON(), nullable=False),
		sa.Column("source_version_id", sa.Uuid(), nullable=True),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
		sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(
			["source_version_id"], ["interface_versions.id"], ondelete="SET NULL"
		),
		sa.PrimaryKeyConstraint("id"),
		sa.UniqueConstraint(
			"project_id", "version_number", name="uq_interface_versions_project_id_version_number"
		),
	)
	op.create_index("ix_interface_versions_project_id", "interface_versions", ["project_id"])

	with op.batch_alter_table("projects") as batch_op:
		batch_op.add_column(sa.Column("current_interface_version_id", sa.Uuid(), nullable=True))
		batch_op.create_foreign_key(
			"fk_projects_current_interface_version_id",
			"interface_versions",
			["current_interface_version_id"],
			["id"],
			ondelete="SET NULL",
		)

	with op.batch_alter_table("nodes") as batch_op:
		batch_op.add_column(sa.Column("interface_version_id", sa.Uuid(), nullable=True))
		batch_op.create_foreign_key(
			"fk_nodes_interface_version_id",
			"interface_versions",
			["interface_version_id"],
			["id"],
			ondelete="SET NULL",
		)

	# A taste prior is now on unless a project's interface switches it off.
	with op.batch_alter_table("taste_priors") as batch_op:
		batch_op.drop_column("is_enabled")


def downgrade() -> None:
	"""Drop interface versions and give taste priors their own switch back."""
	with op.batch_alter_table("taste_priors") as batch_op:
		batch_op.add_column(
			sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
		)

	with op.batch_alter_table("nodes") as batch_op:
		batch_op.drop_constraint("fk_nodes_interface_version_id", type_="foreignkey")
		batch_op.drop_column("interface_version_id")

	with op.batch_alter_table("projects") as batch_op:
		batch_op.drop_constraint("fk_projects_current_interface_version_id", type_="foreignkey")
		batch_op.drop_column("current_interface_version_id")

	op.drop_table("interface_versions")
