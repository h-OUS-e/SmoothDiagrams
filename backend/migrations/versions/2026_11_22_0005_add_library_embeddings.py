"""Give library items an embedding, for sorting the library by visual similarity.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
	"""Add the embedding of a library item and what it was computed from."""
	with op.batch_alter_table("library_items") as batch_op:
		batch_op.add_column(sa.Column("embedding", sa.LargeBinary(), nullable=True))
		batch_op.add_column(sa.Column("embedding_model", sa.Text(), nullable=True))
		batch_op.add_column(sa.Column("embedding_source_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
	"""Drop the embedding of a library item."""
	with op.batch_alter_table("library_items") as batch_op:
		batch_op.drop_column("embedding_source_id")
		batch_op.drop_column("embedding_model")
		batch_op.drop_column("embedding")
