"""Shapes of the data the server sends and receives over HTTP."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from smooth_diagrams.database.models import NodeKind, NodeStatus


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


# ---------------------------------------------------------------------------
# Nodes and steps
# ---------------------------------------------------------------------------


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
	created_at: datetime
	# Number of steps that were not rejected.
	step_count: int
	# Render of the newest step that was not rejected.
	render_svg: str | None


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
	created_at: datetime
	parameter_values: dict[str, Any]
	steps: list[StepDetail]
	# The step this node starts from, when it continues another node.
	parent_step: StepDetail | None


class PieceDetail(ApiModel):
	id: uuid.UUID
	project_id: uuid.UUID
	name: str
	created_at: datetime
	nodes: list[NodeSummary]


class ParameterValuesInput(BaseModel):
	parameter_values: dict[str, float | str | bool]
