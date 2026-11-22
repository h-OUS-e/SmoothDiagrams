"""Add assets, the library, priors, taste priors, and taste reasons.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

library_item_kind = sa.Enum("image", "node", name="libraryitemkind", native_enum=False, length=32)
taste_prior_kind = sa.Enum(
	"text", "image", "skill", name="tastepriorkind", native_enum=False, length=32
)


def upgrade() -> None:
	"""Create the tables for references and give nodes an image and a taste reason."""
	op.create_table(
		"assets",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("file_name", sa.Text(), nullable=False),
		sa.Column("media_type", sa.Text(), nullable=False),
		sa.Column("storage_key", sa.Text(), nullable=False),
		sa.Column("byte_size", sa.Integer(), nullable=False),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
		sa.PrimaryKeyConstraint("id"),
	)

	op.create_table(
		"library_items",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("kind", library_item_kind, nullable=False),
		sa.Column("name", sa.Text(), nullable=False),
		sa.Column("asset_id", sa.Uuid(), nullable=True),
		sa.Column("node_id", sa.Uuid(), nullable=True),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
		sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
		sa.PrimaryKeyConstraint("id"),
	)
	op.create_index("ix_library_items_node_id", "library_items", ["node_id"])

	op.create_table(
		"priors",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("project_id", sa.Uuid(), nullable=False),
		sa.Column("library_item_id", sa.Uuid(), nullable=True),
		sa.Column("name", sa.Text(), nullable=True),
		sa.Column("text_content", sa.Text(), nullable=True),
		sa.Column("prior_note", sa.Text(), nullable=False),
		sa.Column("is_enabled", sa.Boolean(), nullable=False),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
		sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["library_item_id"], ["library_items.id"], ondelete="CASCADE"),
		sa.PrimaryKeyConstraint("id"),
		sa.UniqueConstraint(
			"project_id", "library_item_id", name="uq_priors_project_id_library_item_id"
		),
	)
	op.create_index("ix_priors_project_id", "priors", ["project_id"])

	op.create_table(
		"taste_priors",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("kind", taste_prior_kind, nullable=False),
		sa.Column("name", sa.Text(), nullable=False),
		sa.Column("text_content", sa.Text(), nullable=True),
		sa.Column("asset_id", sa.Uuid(), nullable=True),
		sa.Column("is_enabled", sa.Boolean(), nullable=False),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
		sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
		sa.PrimaryKeyConstraint("id"),
	)

	with op.batch_alter_table("nodes") as batch_op:
		batch_op.add_column(sa.Column("image_asset_id", sa.Uuid(), nullable=True))
		batch_op.add_column(sa.Column("taste_reason_candidates", sa.JSON(), nullable=True))
		batch_op.add_column(sa.Column("taste_reason", sa.Text(), nullable=True))
		batch_op.create_foreign_key(
			"fk_nodes_image_asset_id", "assets", ["image_asset_id"], ["id"], ondelete="SET NULL"
		)


def downgrade() -> None:
	"""Drop everything this migration added."""
	with op.batch_alter_table("nodes") as batch_op:
		batch_op.drop_constraint("fk_nodes_image_asset_id", type_="foreignkey")
		batch_op.drop_column("taste_reason")
		batch_op.drop_column("taste_reason_candidates")
		batch_op.drop_column("image_asset_id")

	op.drop_table("taste_priors")
	op.drop_table("priors")
	op.drop_table("library_items")
	op.drop_table("assets")
