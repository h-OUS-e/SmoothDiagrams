"""What an interface version holds: how a project's generations are set up."""

import enum
import uuid
from typing import Self

from pydantic import (
	BaseModel,
	Field,
	StrictBool,
	StrictFloat,
	StrictInt,
	StrictStr,
	model_validator,
)

from smooth_diagrams.generation.prompt_templates import read_prompt
from smooth_diagrams.model_catalog import is_known_model

# Where a prompt control's value goes in its instruction.
value_placeholder = "{value}"


class PromptControlKind(enum.StrEnum):
	SLIDER = "slider"
	SELECT = "select"
	TOGGLE = "toggle"
	TEXT = "text"


class PromptControl(BaseModel):
	"""A control the director sets, whose value is told to the model as an instruction."""

	id: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=40)
	label: str = Field(min_length=1, max_length=80)
	kind: PromptControlKind

	# What the model is told; "{value}" stands for the control's value.
	instruction: str = Field(min_length=1)
	value: StrictBool | StrictInt | StrictFloat | StrictStr

	# Range of a slider.
	min: float | None = None
	max: float | None = None
	step: float | None = None

	# Choices of a select.
	options: list[str] | None = None

	@model_validator(mode="after")
	def check_kind(self) -> Self:
		"""Require the fields and the value type that the control's kind needs."""
		is_number = isinstance(self.value, (int, float)) and not isinstance(self.value, bool)

		match self.kind:
			case PromptControlKind.SLIDER:
				if self.min is None or self.max is None or self.step is None:
					raise ValueError("A slider needs min, max, and step.")
				if self.min >= self.max or self.step <= 0:
					raise ValueError("A slider needs min below max and a positive step.")
				if not is_number or not self.min <= self.value <= self.max:
					raise ValueError("A slider's value must be a number from min to max.")
			case PromptControlKind.SELECT:
				if not self.options:
					raise ValueError("A select needs at least one option.")
				if self.value not in self.options:
					raise ValueError("A select's value must be one of its options.")
			case PromptControlKind.TOGGLE:
				if not isinstance(self.value, bool):
					raise ValueError("A toggle's value must be true or false.")
			case PromptControlKind.TEXT:
				if not isinstance(self.value, str):
					raise ValueError("A text control's value must be text.")
		return self

	def render(self) -> str | None:
		"""Return the instruction with the value filled in, or None when there is nothing to say."""
		# A toggle speaks only when it is on, and a text control only when it holds text.
		if self.kind == PromptControlKind.TOGGLE:
			return self.instruction if self.value else None
		if self.kind == PromptControlKind.TEXT and str(self.value).strip() == "":
			return None

		value = f"{self.value:g}" if isinstance(self.value, float) else str(self.value)
		return self.instruction.replace(value_placeholder, value)


class PromptTemplates(BaseModel):
	"""Prompt text the director can rewrite for a project."""

	# Standing instructions for every generation of the project; empty by default.
	direction: str = ""

	# How the model works when it draws step by step, and when it draws in one pass.
	step_by_step: str
	single_pass: str


class InterfaceSettings(BaseModel):
	"""A project's setup for directing, stored whole in each interface version."""

	model: str
	is_step_by_step: bool = True
	offers_taste_reasons: bool = True
	prompt_templates: PromptTemplates
	prompt_controls: list[PromptControl] = Field(default_factory=list)

	# Taste priors switched off for this project; every other taste prior applies.
	disabled_taste_prior_ids: list[uuid.UUID] = Field(default_factory=list)

	@model_validator(mode="after")
	def check_settings(self) -> Self:
		"""Require a model this app offers and prompt controls with distinct ids."""
		if not is_known_model(self.model):
			raise ValueError(f'The model "{self.model}" is not one this app offers.')

		control_ids = [control.id for control in self.prompt_controls]
		if len(control_ids) != len(set(control_ids)):
			raise ValueError("Prompt controls need distinct ids.")
		return self


def build_default_settings(default_model: str) -> InterfaceSettings:
	"""Return the settings a project starts with when it copies no other interface."""
	return InterfaceSettings(
		model=default_model,
		prompt_templates=PromptTemplates(
			step_by_step=read_prompt("step_by_step"),
			single_pass=read_prompt("single_pass"),
		),
		prompt_controls=[
			PromptControl(
				id="ratio",
				label="Ratio",
				kind=PromptControlKind.SELECT,
				instruction=("Give the diagram a viewBox whose width to height ratio is {value}."),
				value="4:3",
				options=[
					"4:3",
					"3:2",
					"16:9",
					"1:1 (square post)",
					"4:5 (portrait post)",
					"9:16 (story)",
					"7:5 (postcard)",
				],
			),
			PromptControl(
				id="media_type",
				label="Media type",
				kind=PromptControlKind.SELECT,
				instruction=(
					"The diagram is {value}. A still diagram declares no animation; "
					"an animated one must declare one and move."
				),
				value="still",
				options=["still", "animated"],
			),
			PromptControl(
				id="novelty",
				label="Novelty",
				kind=PromptControlKind.SLIDER,
				instruction=(
					"Novelty is {value} out of 100. At 0 stay as close to the priors as you can; "
					"at 100 depart from them boldly while keeping the director's taste."
				),
				value=30,
				min=0,
				max=100,
				step=5,
			),
		],
	)
