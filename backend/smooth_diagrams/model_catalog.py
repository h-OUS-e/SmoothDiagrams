"""The models a director can choose for a generation."""

import enum

from pydantic import BaseModel


class ModelVendor(enum.StrEnum):
	"""Whose model it is, which decides the program a call runs through."""

	ANTHROPIC = "anthropic"
	OPENAI = "openai"


class ModelOption(BaseModel):
	"""One selectable model."""

	# Exact model id, so the label always names the version that runs.
	id: str
	label: str
	vendor: ModelVendor
	# Something the director should know before choosing the model.
	note: str | None = None


class ModelCatalog(BaseModel):
	"""Every selectable model and the one used when none is chosen."""

	default_model: str
	models: list[ModelOption]


model_options = [
	ModelOption(id="claude-opus-5-5", label="Claude Opus 5.5", vendor=ModelVendor.ANTHROPIC),
	ModelOption(
		id="claude-fable-5-2",
		label="Claude Fable 5.2",
		vendor=ModelVendor.ANTHROPIC,
		note=(
			"Depending on your plan, Fable can be billed to usage credits instead of your "
			"plan's included limits, and this app cannot ask you first."
		),
	),
	ModelOption(id="claude-sonnet-5-5", label="Claude Sonnet 5.5", vendor=ModelVendor.ANTHROPIC),
	ModelOption(id="claude-haiku-5-5", label="Claude Haiku 5.5", vendor=ModelVendor.ANTHROPIC),
	# The ids and names Codex lists for a ChatGPT plan login; checked on 2026-11-22.
	ModelOption(id="gpt-6-astra", label="GPT-6-Astra", vendor=ModelVendor.OPENAI),
	ModelOption(id="gpt-5.6-sol", label="GPT-5.6-Sol", vendor=ModelVendor.OPENAI),
	ModelOption(id="gpt-5.6-terra", label="GPT-5.6-Terra", vendor=ModelVendor.OPENAI),
	ModelOption(id="gpt-5.6-luna", label="GPT-5.6-Luna", vendor=ModelVendor.OPENAI),
]


def find_model(model_id: str) -> ModelOption | None:
	"""Return the selectable model with an id, or None when there is none."""
	return next((option for option in model_options if option.id == model_id), None)


def is_known_model(model_id: str) -> bool:
	"""Return whether a model id is one of the selectable models."""
	return find_model(model_id) is not None
