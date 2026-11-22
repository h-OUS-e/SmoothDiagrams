"""The contract every model vendor implements, so the generation session stays vendor-neutral."""

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from smooth_diagrams.generation.source_edits import SourceEdit


class ModelCallError(Exception):
	"""A model call failed; the message is shown to the director."""


@dataclass(frozen=True)
class PromptImage:
	"""An image shown to the model alongside a prompt."""

	media_type: str
	data: bytes


@dataclass(frozen=True)
class ToolReply:
	"""What the model reads back after calling a source tool."""

	text: str
	is_error: bool = False


class SourceTools(Protocol):
	"""The two tools through which a model produces steps."""

	async def write_source(self, step_reasoning: str, source: str) -> ToolReply:
		"""Replace the whole source as one step."""
		...

	async def edit_source(self, step_reasoning: str, edits: list[SourceEdit]) -> ToolReply:
		"""Replace exact passages of the source as one step."""
		...


@dataclass(frozen=True)
class ReasoningProgress:
	"""The Step Reasoning of the step being written, as far as it has streamed."""

	text: str


@dataclass(frozen=True)
class TurnEnded:
	"""The model stopped responding to the latest prompt."""

	was_interrupted: bool
	error_message: str | None = None


ProviderEvent = ReasoningProgress | TurnEnded


class ModelSession(Protocol):
	"""One conversation with a model that keeps its context between prompts."""

	async def send(self, prompt: str, images: Sequence[PromptImage] = ()) -> None:
		"""Start a turn with a prompt and the images it refers to, in order."""
		...

	def receive(self) -> AsyncIterator[ProviderEvent]:
		"""Yield the events of the current turn, ending with TurnEnded."""
		...

	async def interrupt(self) -> None:
		"""Cut the current turn short."""
		...


class ModelProvider(Protocol):
	"""A model vendor that can hold conversations and call the source tools."""

	def open_session(
		self, *, system_prompt: str, model: str, source_tools: SourceTools
	) -> AbstractAsyncContextManager[ModelSession]:
		"""Open a conversation that lasts for one generation."""
		...

	async def complete(self, *, system_prompt: str, prompt: str, model: str) -> str:
		"""Return the answer to one prompt, with no tools and no memory."""
		...
