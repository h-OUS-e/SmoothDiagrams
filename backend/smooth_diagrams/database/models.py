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
	Float,
	ForeignKey,
	Integer,
	LargeBinary,
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


class LibraryItemKind(enum.StrEnum):
	IMAGE = "image"
	NODE = "node"


class TastePriorKind(enum.StrEnum):
	TEXT = "text"
	IMAGE = "image"
	SKILL = "skill"


class ExportFormat(enum.StrEnum):
	SVELTE = "svelte"
	SVG = "svg"
	PNG = "png"
	JPEG = "jpeg"


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

	# The interface version that the next generation of the project uses.
	current_interface_version_id: Mapped[uuid.UUID | None] = mapped_column(
		ForeignKey(
			"interface_versions.id",
			ondelete="SET NULL",
			name="fk_projects_current_interface_version_id",
			use_alter=True,
		)
	)
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

	# The image an uploaded node holds instead of source.
	image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
		ForeignKey("assets.id", ondelete="SET NULL", name="fk_nodes_image_asset_id")
	)

	# The interface version whose settings made this node.
	interface_version_id: Mapped[uuid.UUID | None] = mapped_column(
		ForeignKey(
			"interface_versions.id", ondelete="SET NULL", name="fk_nodes_interface_version_id"
		)
	)

	# Why the director continued from the parent node: the reasons offered, and the one picked.
	taste_reason_candidates: Mapped[list[str] | None] = mapped_column(JSON)
	taste_reason: Mapped[str | None] = mapped_column(Text)
	created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=current_time)

	piece: Mapped[Piece] = relationship(back_populates="nodes")
	steps: Mapped[list["Step"]] = relationship(
		back_populates="node",
		cascade="all, delete-orphan",
		order_by="Step.step_index",
		foreign_keys="Step.node_id",
	)
	parent_step: Mapped["Step | None"] = relationship(foreign_keys=[parent_step_id])
	image_asset: Mapped["Asset | None"] = relationship(foreign_keys=[image_asset_id])
	exports: Mapped[list["Export"]] = relationship(
		back_populates="node", cascade="all, delete-orphan", order_by="Export.created_at"
	)


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


class Export(Base):
	"""One download of a node, with the settings that make the same file again."""

	__tablename__ = "exports"

	id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
	node_id: Mapped[uuid.UUID] = mapped_column(
		ForeignKey("nodes.id", ondelete="CASCADE"), index=True
	)

	# The step of the node that was exported.
	step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("steps.id", ondelete="SET NULL"))
	format: Mapped[ExportFormat] = mapped_column(string_enum(ExportFormat))

	# The exposed parameter values and the animation clock, in seconds, the file was made with.
	parameter_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
	animation_time: Mapped[float] = mapped_column(Float, default=0.0)

	# Size of a PNG or JPEG in pixels; empty for the formats that have no fixed size.
	pixel_width: Mapped[int | None] = mapped_column(Integer)
	pixel_height: Mapped[int | None] = mapped_column(Integer)
	created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=current_time)

	node: Mapped[Node] = relationship(back_populates="exports")


class Asset(Base):
	"""A file the director brought into the app, kept in the file store."""

	__tablename__ = "assets"

	id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
	file_name: Mapped[str] = mapped_column(Text)
	media_type: Mapped[str] = mapped_column(Text)

	# Where the file store keeps the bytes.
	storage_key: Mapped[str] = mapped_column(Text)
	byte_size: Mapped[int] = mapped_column(Integer)
	created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=current_time)


class LibraryItem(Base):
	"""A reference image or a node, shared across projects."""

	__tablename__ = "library_items"

	id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
	kind: Mapped[LibraryItemKind] = mapped_column(string_enum(LibraryItemKind))
	name: Mapped[str] = mapped_column(Text)
	asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
	node_id: Mapped[uuid.UUID | None] = mapped_column(
		ForeignKey("nodes.id", ondelete="CASCADE"), index=True
	)

	# What the item looks like to the embedding model, as float32 bytes, for sorting by similarity.
	embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
	embedding_model: Mapped[str | None] = mapped_column(Text)

	# The asset or step the embedding was computed from; another one means it is out of date.
	embedding_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
	created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=current_time)

	asset: Mapped[Asset | None] = relationship()
	node: Mapped[Node | None] = relationship()


class Prior(Base):
	"""A reference a project uses to guide generation: a library item, or text of its own."""

	__tablename__ = "priors"
	__table_args__ = (
		UniqueConstraint(
			"project_id", "library_item_id", name="uq_priors_project_id_library_item_id"
		),
	)

	id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
	project_id: Mapped[uuid.UUID] = mapped_column(
		ForeignKey("projects.id", ondelete="CASCADE"), index=True
	)

	# Empty for a text prior, which carries its own name and text instead.
	library_item_id: Mapped[uuid.UUID | None] = mapped_column(
		ForeignKey("library_items.id", ondelete="CASCADE")
	)
	name: Mapped[str | None] = mapped_column(Text)
	text_content: Mapped[str | None] = mapped_column(Text)

	prior_note: Mapped[str] = mapped_column(Text, default="")
	is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
	created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=current_time)

	library_item: Mapped[LibraryItem | None] = relationship()


class TastePrior(Base):
	"""A prior kept outside any project that guides taste in all of them."""

	__tablename__ = "taste_priors"

	id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
	kind: Mapped[TastePriorKind] = mapped_column(string_enum(TastePriorKind))
	name: Mapped[str] = mapped_column(Text)
	text_content: Mapped[str | None] = mapped_column(Text)
	asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
	created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=current_time)

	asset: Mapped[Asset | None] = relationship()


class InterfaceVersion(Base):
	"""One saved state of a project's interface; it never changes once it produced work."""

	__tablename__ = "interface_versions"
	__table_args__ = (
		UniqueConstraint(
			"project_id", "version_number", name="uq_interface_versions_project_id_version_number"
		),
	)

	id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
	project_id: Mapped[uuid.UUID] = mapped_column(
		ForeignKey("projects.id", ondelete="CASCADE"), index=True
	)
	version_number: Mapped[int] = mapped_column(Integer)

	# The whole of the settings, in the shape of InterfaceSettings.
	settings: Mapped[dict[str, Any]] = mapped_column(JSON)

	# The version these settings were first copied from, in this project or another.
	source_version_id: Mapped[uuid.UUID | None] = mapped_column(
		ForeignKey("interface_versions.id", ondelete="SET NULL")
	)
	created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=current_time)
