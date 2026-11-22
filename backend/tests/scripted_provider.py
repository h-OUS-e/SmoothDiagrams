"""A model provider that plays back scripted turns, so tests need no real model."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from smooth_diagrams.providers.base import ModelSession, ProviderEvent, SourceTools, TurnEnded

# One scripted turn: it calls the source tools the way a model would.
ScriptedTurn = Callable[[SourceTools], Awaitable[None]]


class ScriptedSession:
	"""Plays one scripted turn per prompt and records the prompts it was sent."""

	def __init__(self, turns: list[ScriptedTurn], source_tools: SourceTools, prompts: list[str]):
		self._turns = turns
		self._source_tools = source_tools
		self._prompts = prompts
		self._interrupted = asyncio.Event()

	async def send(self, prompt: str) -> None:
		self._prompts.append(prompt)
		self._interrupted.clear()

	async def receive(self) -> AsyncIterator[ProviderEvent]:
		if not self._turns:
			yield TurnEnded(was_interrupted=False)
			return

		# Run the turn until it finishes or the session is interrupted.
		turn_task = asyncio.ensure_future(self._turns.pop(0)(self._source_tools))
		interrupt_task = asyncio.ensure_future(self._interrupted.wait())
		await asyncio.wait({turn_task, interrupt_task}, return_when=asyncio.FIRST_COMPLETED)

		was_interrupted = not turn_task.done()
		for task in (turn_task, interrupt_task):
			task.cancel()
		yield TurnEnded(was_interrupted=was_interrupted)

	async def interrupt(self) -> None:
		self._interrupted.set()


class ScriptedProvider:
	"""Opens sessions that play the given turns in order."""

	def __init__(self, turns: list[ScriptedTurn]) -> None:
		self._turns = turns
		self.prompts: list[str] = []
		self.system_prompts: list[str] = []

	@asynccontextmanager
	async def open_session(
		self, *, system_prompt: str, model: str, source_tools: SourceTools
	) -> AsyncIterator[ModelSession]:
		self.system_prompts.append(system_prompt)
		yield ScriptedSession(self._turns, source_tools, self.prompts)
