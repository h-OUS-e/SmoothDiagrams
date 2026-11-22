"""Shapes of the data the server sends and receives over HTTP."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from smooth_diagrams.database.models import (
	ExportFormat,
	LibraryItemKind,
	NodeKind,
	NodeStatus,
	TastePriorKind,
)
from smooth_diagrams.interface_settings import InterfaceSettings


class ApiModel(BaseModel):
	"""Base for response models, which can be built straight from database rows."""

	model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Projects and pieces
# ---------------------------------------------------------------------------


class PieceSummary(ApiModel):
	id: uuid.UUID
	project_id: uuid.UUID
	name: str
	created_at: datetime


class ProjectSummary(ApiModel):
	id: uuid.UUID
	name: str
	created_at: datetime
	piece_count: int
	# Render of the newest step in the project, shown as the project's cover.
	cover_svg: str | None


class ProjectDetail(ApiModel):
	id: uuid.UUID
	name: str
	created_at: datetime
	pieces: list[PieceSummary]


class NameInput(BaseModel):
	name: str = Field(min_length=1, max_length=200)


class ProjectInput(NameInput):
	# The interface version to copy into the new project; none starts it from the defaults.
	interface_version_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Nodes, steps, and exports
# ---------------------------------------------------------------------------

# Export formats that are made of pixels and so have a size.
pixel_formats = (ExportFormat.PNG, ExportFormat.JPEG)

# Longest side an exported image may have, in pixels; browsers cannot draw larger ones.
pixel_size_limit = 16384


class StepDetail(ApiModel):
	id: uuid.UUID
	node_id: uuid.UUID
	step_index: int
	source: str
	step_reasoning: str
	render_svg: str
	is_rejected: bool
	rejection_reason: str | None
	created_at: datetime


class ExportDetail(ApiModel):
	id: uuid.UUID
	node_id: uuid.UUID
	# The step that was exported; null once that step is gone.
	step_id: uuid.UUID | None
	format: ExportFormat
	parameter_values: dict[str, Any]
	animation_time: float
	pixel_width: int | None
	pixel_height: int | None
	created_at: datetime


class NodeSummary(ApiModel):
	id: uuid.UUID
	piece_id: uuid.UUID
	parent_node_id: uuid.UUID | None
	parent_step_id: uuid.UUID | None
	kind: NodeKind
	status: NodeStatus
	prompt: str
	model: str | None
	is_step_by_step: bool
	failure_message: str | None
	image_asset_id: uuid.UUID | None
	interface_version_id: uuid.UUID | None
	created_at: datetime
	# Number of steps that were not rejected.
	step_count: int
	# Render of the newest step that was not rejected.
	render_svg: str | None
	# Number of times the node was exported.
	export_count: int


class NodeDetail(ApiModel):
	id: uuid.UUID
	piece_id: uuid.UUID
	parent_node_id: uuid.UUID | None
	parent_step_id: uuid.UUID | None
	kind: NodeKind
	status: NodeStatus
	prompt: str
	model: str | None
	is_step_by_step: bool
	failure_message: str | None
	image_asset_id: uuid.UUID | None
	interface_version_id: uuid.UUID | None
	taste_reason_candidates: list[str] | None
	taste_reason: str | None
	created_at: datetime
	parameter_values: dict[str, Any]
	steps: list[StepDetail]
	# The step this node starts from, when it continues another node.
	parent_step: StepDetail | None
	exports: list[ExportDetail]


class PieceDetail(ApiModel):
	id: uuid.UUID
	project_id: uuid.UUID
	name: str
	created_at: datetime
	nodes: list[NodeSummary]


class ParameterValuesInput(BaseModel):
	parameter_values: dict[str, float | str | bool]


class ExportInput(BaseModel):
	"""What the director exported: a step in a format, as it looked at that moment."""

	step_id: uuid.UUID
	format: ExportFormat
	parameter_values: dict[str, float | str | bool] = Field(default_factory=dict)
	animation_time: float = Field(default=0.0, ge=0)
	pixel_width: int | None = Field(default=None, gt=0, le=pixel_size_limit)
	pixel_height: int | None = Field(default=None, gt=0, le=pixel_size_limit)

	@model_validator(mode="after")
	def check_pixel_size(self) -> "ExportInput":
		"""Require a pixel size for the formats made of pixels, and refuse one for the others."""
		has_size = self.pixel_width is not None and self.pixel_height is not None
		has_no_size = self.pixel_width is None and self.pixel_height is None
		if self.format in pixel_formats and not has_size:
			raise ValueError("A PNG or JPEG export needs a width and a height in pixels.")
		if self.format not in pixel_formats and not has_no_size:
			raise ValueError("Only a PNG or JPEG export has a size in pixels.")
		return self


class TasteReasonInput(BaseModel):
	# The reason the director picked or wrote; null clears it.
	taste_reason: str | None = Field(default=None, max_length=1000)


class TasteReasonCandidates(BaseModel):
	candidates: list[str]


# ---------------------------------------------------------------------------
# Library, priors, and taste priors
# ---------------------------------------------------------------------------


class LibraryItemDetail(ApiModel):
	id: uuid.UUID
	kind: LibraryItemKind
	name: str
	asset_id: uuid.UUID | None
	node_id: uuid.UUID | None
	created_at: datetime
	# Render of the newest step of a node item; null for an image item.
	render_svg: str | None


class LibraryNodeInput(BaseModel):
	node_id: uuid.UUID


class PriorDetail(ApiModel):
	id: uuid.UUID
	project_id: uuid.UUID
	name: str
	# Text of a text prior; null for a prior that points at a library item.
	text_content: str | None
	library_item: LibraryItemDetail | None
	prior_note: str
	is_enabled: bool
	created_at: datetime


class PriorInput(BaseModel):
	"""Either a library item to use as a prior, or the name and text of a text prior."""

	library_item_id: uuid.UUID | None = None
	name: str | None = Field(default=None, min_length=1, max_length=200)
	text_content: str | None = None


class PriorChanges(BaseModel):
	"""Fields of a prior to change; the ones left out stay as they are."""

	name: str | None = Field(default=None, min_length=1, max_length=200)
	text_content: str | None = None
	prior_note: str | None = None
	is_enabled: bool | None = None


class TastePriorDetail(ApiModel):
	id: uuid.UUID
	kind: TastePriorKind
	name: str
	text_content: str | None
	asset_id: uuid.UUID | None
	created_at: datetime


class TastePriorInput(BaseModel):
	"""A taste prior made of text: plain taste notes, or a skill document."""

	kind: TastePriorKind
	name: str = Field(min_length=1, max_length=200)
	text_content: str = Field(min_length=1)


class TastePriorChanges(BaseModel):
	"""Fields of a taste prior to change; the ones left out stay as they are."""

	name: str | None = Field(default=None, min_length=1, max_length=200)
	text_content: str | None = None


# ---------------------------------------------------------------------------
# Interface versions
# ---------------------------------------------------------------------------


class InterfaceVersionSummary(BaseModel):
	id: uuid.UUID
	version_number: int
	created_at: datetime
	# Number of nodes made with this version.
	node_count: int
	is_current: bool


class InterfaceState(BaseModel):
	"""A project's current interface settings and a summary of all its versions."""

	current_version_id: uuid.UUID
	version_number: int
	settings: InterfaceSettings
	versions: list[InterfaceVersionSummary]


class InterfaceSource(BaseModel):
	"""An interface version a new project can start from."""

	id: uuid.UUID
	project_id: uuid.UUID
	project_name: str
	version_number: int
	created_at: datetime


class RestoreInput(BaseModel):
	interface_version_id: uuid.UUID
