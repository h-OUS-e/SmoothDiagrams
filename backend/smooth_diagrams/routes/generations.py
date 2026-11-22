"""WebSocket route that runs one generation per connection."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from smooth_diagrams.generation.messages import (
	GenerationEvent,
	PauseCommand,
	RedirectCommand,
	RejectStepCommand,
	ResumeCommand,
	StartCommand,
	StepOutcomeCommand,
	StopCommand,
	steering_command_adapter,
)
from smooth_diagrams.generation.session import FrontendGoneError, GenerationSession

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket close code for a message that breaks the protocol.
policy_violation_code = 1008

# Generations being wound down after their connection was dropped, kept so they are not lost.
settling_tasks: set[asyncio.Task[None]] = set()


async def settle_generation(session: GenerationSession, run_task: asyncio.Task[None]) -> None:
	"""Stop a generation and wait until its node has a final status."""
	await session.stop()
	await run_task


async def relay_commands(websocket: WebSocket, session: GenerationSession) -> None:
	"""Pass the director's commands to the session until the frontend disconnects."""
	while True:
		try:
			command = steering_command_adapter.validate_python(await websocket.receive_json())
		except WebSocketDisconnect:
			return
		except (ValidationError, ValueError):
			logger.warning("Ignored a command that does not follow the protocol")
			continue

		match command:
			case StepOutcomeCommand():
				session.report_step_outcome(command)
			case PauseCommand():
				await session.pause()
			case ResumeCommand():
				await session.resume()
			case RedirectCommand():
				await session.redirect(command.prompt)
			case RejectStepCommand():
				await session.reject_latest_step(command.reason)
			case StopCommand():
				await session.stop()


@router.websocket("/generations")
async def run_generation(websocket: WebSocket) -> None:
	"""Run one generation: read the start command, then stream events and take commands."""
	await websocket.accept()

	# Read the command that says what to generate.
	try:
		start = StartCommand.model_validate(await websocket.receive_json())
	except WebSocketDisconnect:
		return
	except (ValidationError, ValueError):
		await websocket.close(code=policy_violation_code, reason="Expected a start command")
		return

	async def emit(event: GenerationEvent) -> None:
		try:
			await websocket.send_text(event.model_dump_json())
		except (WebSocketDisconnect, RuntimeError) as error:
			raise FrontendGoneError from error

	session = GenerationSession(
		start=start,
		provider=websocket.app.state.provider,
		session_factory=websocket.app.state.session_factory,
		settings=websocket.app.state.settings,
		emit=emit,
	)

	# Run the generation and the command relay side by side until either one ends.
	run_task = asyncio.create_task(session.run())
	relay_task = asyncio.create_task(relay_commands(websocket, session))
	try:
		await asyncio.wait({run_task, relay_task}, return_when=asyncio.FIRST_COMPLETED)

		# Stop a generation whose frontend went away, so its node gets a final status.
		if not run_task.done():
			await session.stop()

		# Shield the generation, because cancelling this handler would otherwise cancel it too.
		await asyncio.shield(run_task)
	except asyncio.CancelledError:
		# The server dropped this connection, so wind the generation down on its own task.
		settling_task = asyncio.ensure_future(settle_generation(session, run_task))
		settling_tasks.add(settling_task)
		settling_task.add_done_callback(settling_tasks.discard)
		raise
	finally:
		relay_task.cancel()

	try:
		await websocket.close()
	except RuntimeError:
		pass
