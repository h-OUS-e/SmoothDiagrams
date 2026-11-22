"""A model provider that plays back scripted turns, so tests need no real model."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

from smooth_diagrams.providers.base import (
	ModelSession,
	PromptImage,
	ProviderEvent,
	SourceTools,
	TurnEnded,
)

# One scripted turn: it calls the source tools the way a model would.
ScriptedTurn = Callable[[SourceTools], Awaitable[None]]


class ScriptedSession:
	"""Plays one scripted turn per prompt and records what it was sent."""

	def __init__(self, provider: "ScriptedProvider", source_tools: SourceTools) -> None:
		self._provider = provider
		self._source_tools = source_tools
		self._interrupted = asyncio.Event()

	async def send(self, prompt: str, images: Sequence[PromptImage] = ()) -> None:
		self._provider.prompts.append(prompt)
		self._provider.images.append(list(images))
		self._interrupted.clear()

	async def receive(self) -> AsyncIterator[ProviderEvent]:
		if not self._provider.turns:
			yield TurnEnded(was_interrupted=False)
			return

		# Run the turn until it finishes or the session is interrupted.
		turn_task = asyncio.ensure_future(self._provider.turns.pop(0)(self._source_tools))
		interrupt_task = asyncio.ensure_future(self._interrupted.wait())
		await asyncio.wait({turn_task, interrupt_task}, return_when=asyncio.FIRST_COMPLETED)

		was_interrupted = not turn_task.done()
		for task in (turn_task, interrupt_task):
			task.cancel()
		yield TurnEnded(was_interrupted=was_interrupted)

	async def interrupt(self) -> None:
		self._interrupted.set()


class ScriptedProvider:
	"""Opens sessions that play the given turns in order, and answers one-off prompts."""

	def __init__(self, turns: list[ScriptedTurn]) -> None:
		self.turns = turns

		# Everything the sessions were sent, one entry per turn.
		self.prompts: list[str] = []
		self.images: list[list[PromptImage]] = []
		self.system_prompts: list[str] = []
		self.models: list[str] = []

		# The answer to the next one-off prompt, and the one-off prompts received.
		self.completion = "[]"
		self.completion_prompts: list[str] = []

	@asynccontextmanager
	async def open_session(
		self, *, system_prompt: str, model: str, source_tools: SourceTools
	) -> AsyncIterator[ModelSession]:
		self.system_prompts.append(system_prompt)
		self.models.append(model)
		yield ScriptedSession(self, source_tools)

	async def complete(self, *, system_prompt: str, prompt: str, model: str) -> str:
		self.completion_prompts.append(prompt)
		return self.completion
