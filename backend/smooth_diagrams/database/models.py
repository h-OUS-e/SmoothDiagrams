"""Database tables. Column types are portable between SQLite and Postgres."""

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
	JSON,
	Boolean,
	DateTime,
	Enum,
	ForeignKey,
	Integer,
	Text,
	UniqueConstraint,
	Uuid,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def current_time() -> datetime:
	"""Return the current time in UTC."""
	return datetime.now(UTC)


class UtcDateTime(TypeDecorator[datetime]):
	"""Store datetimes in UTC and return them timezone-aware, which SQLite does not do itself."""

	impl = DateTime(timezone=True)
	cache_ok = True

	def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
		if value is None:
			return None
		if value.tzinfo is None:
			raise ValueError("Datetimes must be timezone-aware")
		return value.astimezone(UTC)

	def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
		if value is None:
			return None
		return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class NodeKind(enum.StrEnum):
	GENERATED = "generated"
	UPLOADED = "uploaded"


class NodeStatus(enum.StrEnum):
	GENERATING = "generating"
	FINISHED = "finished"
	STOPPED = "stopped"
	FAILED = "failed"


def string_enum(enum_class: type[enum.StrEnum]) -> Enum:
	"""Return a column type that stores an enum's values as plain strings."""
	return Enum(
		enum_class,
		native_enum=False,
		length=32,
		values_callable=lambda members: [member.value for member in members],
	)


class Base(DeclarativeBase):
	pass


class Project(Base):
	__tablename__ = "projects"

	id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
	name: Mapped[str] = mapped_column(Text)
	created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=current_time)

	pieces: Mapped[list["Piece"]] = relationship(
		back_populates="project", cascade="all, delete-orphan", order_by="Piece.created_at"
	)


class Piece(Base):
	__tablename__ = "pieces"

	id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
	project_id: Mapped[uuid.UUID] = mapped_column(
		ForeignKey("projects.id", ondelete="CASCADE"), index=True
	)
	name: Mapped[str] = mapped_column(Text)
	created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=current_time)

	project: Mapped[Project] = relationship(back_populates="pieces")
	nodes: Mapped[list["Node"]] = relationship(
		back_populates="piece", cascade="all, delete-orphan", order_by="Node.created_at"
	)


class Node(Base):
	__tablename__ = "nodes"

	id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
	piece_id: Mapped[uuid.UUID] = mapped_column(
		ForeignKey("pieces.id", ondelete="CASCADE"), index=True
	)

	# The node this one continues from, and the step of it that this one starts at.
	parent_node_id: Mapped[uuid.UUID | None] = mapped_column(
		ForeignKey("nodes.id", ondelete="SET NULL"), index=True
	)
	parent_step_id: Mapped[uuid.UUID | None] = mapped_column(
		ForeignKey("steps.id", ondelete="SET NULL", name="fk_nodes_parent_step_id", use_alter=True)
	)

	kind: Mapped[NodeKind] = mapped_column(string_enum(NodeKind), default=NodeKind.GENERATED)
	status: Mapped[NodeStatus] = mapped_column(string_enum(NodeStatus))
	prompt: Mapped[str] = mapped_column(Text, default="")
	model: Mapped[str | None] = mapped_column(Text)
	is_step_by_step: Mapped[bool] = mapped_column(Boolean, default=True)
	parameter_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
	failure_message: Mapped[str | None] = mapped_column(Text)
	created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=current_time)

	piece: Mapped[Piece] = relationship(back_populates="nodes")
	steps: Mapped[list["Step"]] = relationship(
		back_populates="node",
		cascade="all, delete-orphan",
		order_by="Step.step_index",
		foreign_keys="Step.node_id",
	)
	parent_step: Mapped["Step | None"] = relationship(foreign_keys=[parent_step_id])


class Step(Base):
	__tablename__ = "steps"
	__table_args__ = (
		UniqueConstraint("node_id", "step_index", name="uq_steps_node_id_step_index"),
	)

	id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
	node_id: Mapped[uuid.UUID] = mapped_column(
		ForeignKey("nodes.id", ondelete="CASCADE"), index=True
	)

	# Position among every step the node ever received, rejected ones included.
	step_index: Mapped[int] = mapped_column(Integer)
	source: Mapped[str] = mapped_column(Text)
	step_reasoning: Mapped[str] = mapped_column(Text)
	render_svg: Mapped[str] = mapped_column(Text)
	is_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
	rejection_reason: Mapped[str | None] = mapped_column(Text)
	created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=current_time)

	node: Mapped[Node] = relationship(back_populates="steps", foreign_keys=[node_id])
