"""The models a director can choose for a generation."""

from pydantic import BaseModel


class ModelOption(BaseModel):
	"""One selectable model."""

	# Exact model id, so the label always names the version that runs.
	id: str
	label: str
	# Something the director should know before choosing the model.
	note: str | None = None


class ModelCatalog(BaseModel):
	"""Every selectable model and the one used when none is chosen."""

	default_model: str
	models: list[ModelOption]


model_options = [
	ModelOption(id="claude-opus-5-5", label="Claude Opus 5.5"),
	ModelOption(
		id="claude-fable-5-2",
		label="Claude Fable 5.2",
		note=(
			"Depending on your plan, Fable can be billed to usage credits instead of your "
			"plan's included limits, and this app cannot ask you first."
		),
	),
	ModelOption(id="claude-sonnet-5-5", label="Claude Sonnet 5.5"),
	ModelOption(id="claude-haiku-5-5", label="Claude Haiku 5.5"),
]


def is_known_model(model_id: str) -> bool:
	"""Return whether a model id is one of the selectable models."""
	return any(option.id == model_id for option in model_options)
