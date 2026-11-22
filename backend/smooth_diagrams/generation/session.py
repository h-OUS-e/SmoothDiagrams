"""Drive one generation: the model proposes steps, the viewer renders them, the director steers."""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from smooth_diagrams.database import queries
from smooth_diagrams.database.engine import SessionFactory
from smooth_diagrams.database.models import Node, NodeStatus, Piece, Step
from smooth_diagrams.generation.messages import (
	GenerationEndedEvent,
	GenerationEvent,
	NodeCreatedEvent,
	PausedEvent,
	ReasoningProgressEvent,
	ResumedEvent,
	StartCommand,
	StepFailedEvent,
	StepOutcomeCommand,
	StepProposedEvent,
	StepRejectedEvent,
	StepSavedEvent,
)
from smooth_diagrams.generation.prompt_builder import (
	build_first_prompt,
	build_redirect_prompt,
	build_reject_prompt,
	build_resume_prompt,
	build_system_prompt,
)
from smooth_diagrams.generation.source_edits import SourceEdit, SourceEditError, apply_source_edits
from smooth_diagrams.model_catalog import is_known_model
from smooth_diagrams.providers.base import (
	ModelProvider,
	ModelSession,
	ReasoningProgress,
	ToolReply,
	TurnEnded,
)
from smooth_diagrams.schemas import NodeDetail, StepDetail
from smooth_diagrams.settings import Settings

logger = logging.getLogger(__name__)

EmitEvent = Callable[[GenerationEvent], Awaitable[None]]

paused_reply = "The director paused the work. End your turn now without calling a tool."
interrupted_reply = "The director interrupted you, so this step was not saved."
failure_limit_reply = "Too many attempts failed in a row. End your turn now."


class FrontendGoneError(Exception):
	"""The frontend can no longer receive events."""


class GenerationStartError(Exception):
	"""A generation cannot start; the message is shown to the director."""


@dataclass(frozen=True)
class Redirect:
	"""The director asked for a new direction."""

	prompt: str


@dataclass(frozen=True)
class Rejection:
	"""The director rejected the latest step."""

	step_reasoning: str
	reason: str | None


Steering = Redirect | Rejection


class GenerationSession:
	"""One generation of one node, from the director's prompt to the node's final status.

	The session implements the source tools the model calls. Every tool call becomes a
	proposed step that is saved only after the viewer reports that it rendered.
	"""

	def __init__(
		self,
		*,
		start: StartCommand,
		provider: ModelProvider,
		session_factory: SessionFactory,
		settings: Settings,
		emit: EmitEvent,
	) -> None:
		self._start = start
		self._provider = provider
		self._session_factory = session_factory
		self._settings = settings
		self._emit_event = emit
		self._model = start.model or settings.default_model

		self._node_id: uuid.UUID | None = None
		self._base_source = ""
		self._current_source = ""
		self._accepted_steps: list[Step] = []
		self._next_step_index = 0

		self._model_session: ModelSession | None = None
		self._is_turn_active = False
		self._pending_outcomes: dict[str, asyncio.Future[StepOutcomeCommand | None]] = {}
		self._consecutive_failures = 0
		self._failure_message: str | None = None

		self._is_paused = False
		self._was_told_to_pause = False
		self._is_stopping = False
		self._steering: Steering | None = None
		self._wake = asyncio.Event()
		self._background_tasks: set[asyncio.Task[None]] = set()

	# -----------------------------------------------------------------------
	# Main loop
	# -----------------------------------------------------------------------

	async def run(self) -> None:
		"""Run the generation to its end and record the node's final status."""
		try:
			node = await self._create_node()
		except GenerationStartError as error:
			await self._emit(GenerationEndedEvent(status=NodeStatus.FAILED, message=str(error)))
			return
		await self._emit(NodeCreatedEvent(node=node))

		try:
			async with self._provider.open_session(
				system_prompt=build_system_prompt(self._start.is_step_by_step),
				model=self._model,
				source_tools=self,
			) as model_session:
				self._model_session = model_session

				# Run turns until no prompt is left to send.
				prompt: str | None = build_first_prompt(self._start.prompt, self._base_source)
				while prompt is not None:
					turn_ended = await self._run_turn(model_session, prompt)
					prompt = await self._choose_next_prompt(turn_ended)
		except Exception as error:
			logger.exception("Generation failed")
			self._failure_message = self._failure_message or f"The model session failed: {error}"
		finally:
			self._model_session = None

		await self._finish()

	async def _run_turn(self, model_session: ModelSession, prompt: str) -> TurnEnded:
		"""Send one prompt and relay the model's progress until its turn ends."""
		turn_ended = TurnEnded(was_interrupted=False)
		self._is_turn_active = True
		try:
			await model_session.send(prompt)
			async for event in model_session.receive():
				if isinstance(event, ReasoningProgress):
					await self._emit(ReasoningProgressEvent(text=event.text))
				else:
					turn_ended = event
		finally:
			self._is_turn_active = False
		return turn_ended

	async def _choose_next_prompt(self, turn_ended: TurnEnded) -> str | None:
		"""Return the prompt for the next turn, or None when the generation is over."""
		if self._is_stopping or self._failure_message:
			return None
		if turn_ended.error_message and not turn_ended.was_interrupted:
			self._failure_message = turn_ended.error_message
			return None

		# Hold a paused generation until the director resumes, steers, or stops it.
		while self._is_paused and self._was_told_to_pause and self._steering is None:
			await self._wake.wait()
			self._wake.clear()
			if self._is_stopping:
				return None

		# Give steering priority over simply carrying on.
		steering, self._steering = self._steering, None
		was_told_to_pause, self._was_told_to_pause = self._was_told_to_pause, False
		if isinstance(steering, Redirect):
			return build_redirect_prompt(steering.prompt, self._current_source)
		if isinstance(steering, Rejection):
			return build_reject_prompt(
				steering.step_reasoning, steering.reason, self._current_source
			)
		if was_told_to_pause or turn_ended.was_interrupted:
			return build_resume_prompt(self._current_source)
		return None

	async def _finish(self) -> None:
		"""Record why the generation ended and tell the frontend."""
		# Release anything still waiting on the viewer.
		self._resolve_pending_outcomes()

		if self._failure_message:
			status = NodeStatus.FAILED
		elif self._is_stopping:
			status = NodeStatus.STOPPED
		elif not self._accepted_steps:
			status = NodeStatus.FAILED
			self._failure_message = "The model ended its turn without drawing a step."
		else:
			status = NodeStatus.FINISHED

		async with self._session_factory() as session:
			node = await session.get(Node, self._node_id)
			if node is not None:
				node.status = status
				node.failure_message = self._failure_message
				await session.commit()

		await self._emit(GenerationEndedEvent(status=status, message=self._failure_message))

	# -----------------------------------------------------------------------
	# Source tools, called by the model
	# -----------------------------------------------------------------------

	async def write_source(self, step_reasoning: str, source: str) -> ToolReply:
		"""Propose a step that replaces the whole source."""
		return await self._propose_step(step_reasoning, source)

	async def edit_source(self, step_reasoning: str, edits: list[SourceEdit]) -> ToolReply:
		"""Propose a step that replaces exact passages of the source."""
		refusal = self._refuse_step()
		if refusal is not None:
			return refusal

		try:
			source = apply_source_edits(self._current_source, edits)
		except SourceEditError as error:
			return await self._register_failure(str(error))
		return await self._propose_step(step_reasoning, source)

	async def _propose_step(self, step_reasoning: str, source: str) -> ToolReply:
		"""Send a step to the viewer and save it once it renders.

		Args:
			step_reasoning: The model's one-line reasoning for the step.
			source: The full diagram source after the step.

		Returns:
			What the model reads back: confirmation, the reason it failed, or a notice to stop.
		"""
		refusal = self._refuse_step()
		if refusal is not None:
			return refusal

		if source == self._current_source:
			return await self._register_failure("This step changes nothing in the source.")
		if step_reasoning.strip() == "":
			return await self._register_failure("The design_note is empty.")

		# Ask the viewer to compile and render the step, and wait for its answer.
		step_token = uuid.uuid4().hex
		outcome_future: asyncio.Future[StepOutcomeCommand | None] = (
			asyncio.get_running_loop().create_future()
		)
		self._pending_outcomes[step_token] = outcome_future
		await self._emit(
			StepProposedEvent(step_token=step_token, source=source, step_reasoning=step_reasoning)
		)
		try:
			outcome = await asyncio.wait_for(outcome_future, self._settings.step_outcome_timeout)
		except TimeoutError:
			return await self._register_failure("The viewer did not report on this step in time.")
		finally:
			self._pending_outcomes.pop(step_token, None)

		# Drop the step when the director steered while it was rendering.
		if outcome is None or self._is_stopping or self._steering is not None:
			return ToolReply(interrupted_reply, is_error=True)

		if not outcome.ok or outcome.render_svg is None:
			return await self._register_failure(outcome.message or "The step did not render.")

		step = await self._save_step(step_reasoning, source, outcome.render_svg)
		await self._emit(StepSavedEvent(step=StepDetail.model_validate(step)))

		if self._is_paused:
			self._was_told_to_pause = True
			return ToolReply(f"Step saved. {paused_reply}")
		return ToolReply("Step saved and rendered.")

	def _refuse_step(self) -> ToolReply | None:
		"""Return the reply that turns a step away, or None when steps are welcome."""
		if self._failure_message:
			return ToolReply(failure_limit_reply, is_error=True)
		if self._is_stopping or self._steering is not None:
			return ToolReply(interrupted_reply, is_error=True)
		if self._is_paused:
			self._was_told_to_pause = True
			return ToolReply(paused_reply, is_error=True)
		return None

	async def _register_failure(self, message: str) -> ToolReply:
		"""Count a failed attempt and return the reply that asks the model to repair it."""
		await self._emit(StepFailedEvent(message=message))
		self._consecutive_failures += 1
		if self._consecutive_failures < self._settings.failure_limit:
			return ToolReply(
				f"This step was not saved. Fix the problem and call a tool again.\n\n{message}",
				is_error=True,
			)

		# Give up after too many failures in a row, and cut the turn short.
		self._failure_message = (
			f"Stopped after {self._consecutive_failures} failed attempts in a row. "
			f"The last problem was:\n{message}"
		)
		self._run_in_background(self._interrupt_turn())
		return ToolReply(failure_limit_reply, is_error=True)

	# -----------------------------------------------------------------------
	# Commands, called for the director
	# -----------------------------------------------------------------------

	def report_step_outcome(self, outcome: StepOutcomeCommand) -> None:
		"""Hand the viewer's verdict on a proposed step to the tool call waiting for it."""
		outcome_future = self._pending_outcomes.get(outcome.step_token)
		if outcome_future is not None and not outcome_future.done():
			outcome_future.set_result(outcome)

	async def pause(self) -> None:
		"""Hold the work once the step being written is saved."""
		if self._is_paused:
			return
		self._is_paused = True
		await self._emit(PausedEvent())

	async def resume(self) -> None:
		"""Let a paused generation carry on."""
		if not self._is_paused:
			return
		self._is_paused = False
		await self._emit(ResumedEvent())
		self._wake.set()

	async def redirect(self, prompt: str) -> None:
		"""Interrupt the model and send it in a new direction."""
		self._steering = Redirect(prompt=prompt)
		await self._steer()

	async def reject_latest_step(self, reason: str | None) -> None:
		"""Remove the newest saved step and ask the model to take another direction."""
		if not self._accepted_steps:
			return
		step = self._accepted_steps.pop()

		# Mark the step rejected and fall back to the source before it.
		async with self._session_factory() as session:
			stored_step = await session.get(Step, step.id)
			if stored_step is not None:
				stored_step.is_rejected = True
				stored_step.rejection_reason = reason
				await session.commit()
		self._current_source = (
			self._accepted_steps[-1].source if self._accepted_steps else self._base_source
		)
		await self._emit(StepRejectedEvent(step_id=step.id))

		self._steering = Rejection(step_reasoning=step.step_reasoning, reason=reason)
		await self._steer()

	async def stop(self) -> None:
		"""End the generation, keeping the steps saved so far."""
		self._is_stopping = True
		self._resolve_pending_outcomes()
		await self._interrupt_turn()
		self._wake.set()

	async def _steer(self) -> None:
		"""Cut the current turn short so the pending steering becomes the next prompt."""
		if self._is_paused:
			self._is_paused = False
			await self._emit(ResumedEvent())
		self._resolve_pending_outcomes()
		await self._interrupt_turn()
		self._wake.set()

	# -----------------------------------------------------------------------
	# Helpers
	# -----------------------------------------------------------------------

	async def _create_node(self) -> NodeDetail:
		"""Create the node being generated and load the source it continues from."""
		async with self._session_factory() as session:
			piece = await session.get(Piece, self._start.piece_id)
			if piece is None:
				raise GenerationStartError("That piece no longer exists.")
			if not is_known_model(self._model):
				raise GenerationStartError(f'The model "{self._model}" is not one this app offers.')

			# Start from the chosen step of the parent node, when continuing one.
			parent_step: Step | None = None
			if self._start.parent_step_id is not None:
				parent_step = await queries.get_step(session, self._start.parent_step_id)
				if parent_step is None or parent_step.is_rejected:
					raise GenerationStartError("The step to continue from no longer exists.")
				self._base_source = parent_step.source
				self._current_source = parent_step.source

			node = Node(
				piece_id=piece.id,
				parent_node_id=parent_step.node_id if parent_step else None,
				parent_step_id=parent_step.id if parent_step else None,
				status=NodeStatus.GENERATING,
				prompt=self._start.prompt,
				model=self._model,
				is_step_by_step=self._start.is_step_by_step,
				parameter_values={},
			)
			session.add(node)
			await session.commit()
			self._node_id = node.id

			stored_node = await queries.get_node(session, node.id)
			return NodeDetail.model_validate(stored_node)

	async def _save_step(self, step_reasoning: str, source: str, render_svg: str) -> Step:
		"""Store a rendered step and make its source the current one."""
		step = Step(
			node_id=self._node_id,
			step_index=self._next_step_index,
			source=source,
			step_reasoning=step_reasoning,
			render_svg=render_svg,
		)
		async with self._session_factory() as session:
			session.add(step)
			await session.commit()

		self._next_step_index += 1
		self._accepted_steps.append(step)
		self._current_source = source
		self._consecutive_failures = 0
		return step

	async def _emit(self, event: GenerationEvent) -> None:
		"""Send an event to the frontend, and stop the generation if it has gone away."""
		try:
			await self._emit_event(event)
		except FrontendGoneError:
			if not self._is_stopping:
				self._is_stopping = True
				self._resolve_pending_outcomes()
				self._run_in_background(self._interrupt_turn())
				self._wake.set()

	async def _interrupt_turn(self) -> None:
		"""Cut the model's current turn short, if one is running."""
		if self._is_turn_active and self._model_session is not None:
			await self._model_session.interrupt()

	def _resolve_pending_outcomes(self) -> None:
		"""Release every tool call that waits on the viewer, marking its step as dropped."""
		for outcome_future in self._pending_outcomes.values():
			if not outcome_future.done():
				outcome_future.set_result(None)

	def _run_in_background(self, work: Awaitable[None]) -> None:
		"""Run work that must not block the caller, keeping a reference until it is done."""
		task = asyncio.ensure_future(work)
		self._background_tasks.add(task)
		task.add_done_callback(self._background_tasks.discard)
