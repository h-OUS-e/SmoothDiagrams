"""Messages exchanged with the frontend over a generation's WebSocket."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from smooth_diagrams.database.models import NodeStatus
from smooth_diagrams.schemas import NodeDetail, StepDetail

# ---------------------------------------------------------------------------
# Commands: frontend to server
# ---------------------------------------------------------------------------


class StartCommand(BaseModel):
	"""Begin a generation; must be the first message on the socket."""

	type: Literal["start"] = "start"
	piece_id: uuid.UUID
	# The step to continue from; leave empty to start a piece's root node.
	parent_step_id: uuid.UUID | None = None
	# The uploaded node to continue from, which has no step to name.
	parent_node_id: uuid.UUID | None = None
	prompt: str = Field(min_length=1)


class StepOutcomeCommand(BaseModel):
	"""Report whether a proposed step compiled and rendered in the viewer."""

	type: Literal["step_outcome"] = "step_outcome"
	step_token: str
	ok: bool
	render_svg: str | None = None
	message: str | None = None


class PauseCommand(BaseModel):
	type: Literal["pause"] = "pause"


class ResumeCommand(BaseModel):
	type: Literal["resume"] = "resume"


class RedirectCommand(BaseModel):
	type: Literal["redirect"] = "redirect"
	prompt: str = Field(min_length=1)


class RejectStepCommand(BaseModel):
	type: Literal["reject_step"] = "reject_step"
	reason: str | None = None


class StopCommand(BaseModel):
	type: Literal["stop"] = "stop"


SteeringCommand = Annotated[
	StepOutcomeCommand
	| PauseCommand
	| ResumeCommand
	| RedirectCommand
	| RejectStepCommand
	| StopCommand,
	Field(discriminator="type"),
]

steering_command_adapter: TypeAdapter[SteeringCommand] = TypeAdapter(SteeringCommand)

# ---------------------------------------------------------------------------
# Events: server to frontend
# ---------------------------------------------------------------------------


class NodeCreatedEvent(BaseModel):
	type: Literal["node_created"] = "node_created"
	node: NodeDetail


class ReasoningProgressEvent(BaseModel):
	"""The Step Reasoning of the step being written, as far as it has streamed."""

	type: Literal["reasoning_progress"] = "reasoning_progress"
	text: str


class StepProposedEvent(BaseModel):
	"""A step for the viewer to compile and render; answer with a step outcome."""

	type: Literal["step_proposed"] = "step_proposed"
	step_token: str
	source: str
	step_reasoning: str


class StepSavedEvent(BaseModel):
	type: Literal["step_saved"] = "step_saved"
	step: StepDetail


class StepFailedEvent(BaseModel):
	"""A proposed step did not render; the model is asked to repair it."""

	type: Literal["step_failed"] = "step_failed"
	message: str


class StepRejectedEvent(BaseModel):
	type: Literal["step_rejected"] = "step_rejected"
	step_id: uuid.UUID


class PausedEvent(BaseModel):
	type: Literal["paused"] = "paused"


class ResumedEvent(BaseModel):
	type: Literal["resumed"] = "resumed"


class GenerationEndedEvent(BaseModel):
	type: Literal["generation_ended"] = "generation_ended"
	status: NodeStatus
	message: str | None = None


GenerationEvent = (
	NodeCreatedEvent
	| ReasoningProgressEvent
	| StepProposedEvent
	| StepSavedEvent
	| StepFailedEvent
	| StepRejectedEvent
	| PausedEvent
	| ResumedEvent
	| GenerationEndedEvent
)
