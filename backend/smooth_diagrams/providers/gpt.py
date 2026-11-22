"""GPT through Codex app-server, signed in with this machine's ChatGPT plan login."""

import base64
import logging
import shutil
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from smooth_diagrams.providers.app_server_client import (
	AppServerClient,
	AppServerError,
	ServerNotification,
	ServerRequest,
)
from smooth_diagrams.providers.base import (
	ModelCallError,
	ModelSession,
	PromptImage,
	ProviderEvent,
	ReasoningProgress,
	SourceTools,
	TurnEnded,
)
from smooth_diagrams.providers.source_tool_calls import (
	SourceToolSpec,
	call_source_tool,
	design_note_field,
	source_tool_specs,
)

logger = logging.getLogger(__name__)

client_name = "smooth_diagrams"
client_title = "SmoothDiagrams"
client_version = "0.1.0"

# Codex settings that keep the director's own Codex setup and this computer away from the model.
isolation_settings = (
	"project_doc_max_bytes=0",
	'web_search="disabled"',
	"skills.include_instructions=false",
	"include_environment_context=false",
	"include_permissions_instructions=false",
)

# Codex features that would give the model tools besides the two source tools.
disabled_features = (
	"shell_tool",
	"unified_exec",
	"apps",
	"plugins",
	"remote_plugin",
	"browser_use",
	"browser_use_external",
	"computer_use",
	"image_generation",
	"multi_agent",
	"view_image",
	"hooks",
	"goals",
	"sleep_tool",
	"skill_search",
	"tool_suggest",
	"memories",
	"workspace_dependencies",
)

# Kinds of work no Codex setting switches off, such as its own agents; starting one stops the turn.
forbidden_item_types = frozenset(
	{
		"collabAgentToolCall",
		"subAgentActivity",
		"commandExecution",
		"mcpToolCall",
		"webSearch",
		"imageGeneration",
	}
)

sign_in_message = (
	"ChatGPT is not signed in. Run `codex login` in a terminal, sign in, and try again."
)
not_installed_message = (
	"Codex is not installed, and GPT runs through it. Install it with "
	"`npm install -g @openai/codex`, run `codex login`, and try again."
)


def describe_turn_error(error: Any) -> str:
	"""Return a message for a turn that failed, from the error Codex reports for it."""
	details = error if isinstance(error, dict) else {}
	message = details.get("message") or "no details were given"

	kind = details.get("codexErrorInfo")
	if kind == "unauthorized":
		return sign_in_message
	if kind == "usageLimitExceeded":
		return f"The usage limit of your ChatGPT plan is reached: {message}"
	return f"GPT ended the turn with an error: {message}"


def describe_forbidden_item(item_type: str) -> str:
	"""Return a message for a turn that was stopped because of what the model started."""
	return (
		f"GPT started something other than drawing ({item_type}), so its turn was stopped. "
		"Try again, or choose another model."
	)


def find_forbidden_item(message: ServerNotification) -> str | None:
	"""Return the kind of forbidden work a notification says has started, on any thread."""
	item = message.params.get("item")
	if message.method != "item/started" or not isinstance(item, dict):
		return None
	item_type = item.get("type")
	return item_type if item_type in forbidden_item_types else None


async def interrupt_turn(client: AppServerClient, thread_id: str, turn_id: str) -> None:
	"""Ask Codex to cut a turn short, which a turn that already ended refuses harmlessly."""
	try:
		await client.request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
	except AppServerError as error:
		logger.info("Codex did not interrupt the turn: %s", error)


def build_turn_input(prompt: str, images: Sequence[PromptImage]) -> list[dict[str, Any]]:
	"""Return a prompt and its images in the shape a turn takes them, images as data addresses."""
	turn_input: list[dict[str, Any]] = [{"type": "text", "text": prompt, "text_elements": []}]
	for image in images:
		encoded = base64.b64encode(image.data).decode("ascii")
		turn_input.append({"type": "image", "url": f"data:{image.media_type};base64,{encoded}"})
	return turn_input


async def answer_server_request(
	client: AppServerClient, request: ServerRequest, source_tools: SourceTools | None
) -> None:
	"""Answer a request Codex makes during a turn: run a source tool, and turn down the rest."""
	if request.method == "item/tool/call" and source_tools is not None:
		reply = await call_source_tool(
			source_tools, str(request.params.get("tool")), request.params.get("arguments")
		)
		result = {
			"contentItems": [{"type": "inputText", "text": reply.text}],
			"success": not reply.is_error,
		}
		await client.respond(request, result)

	# Decline anything Codex wants approved; the thread is set up never to ask, so this is a guard.
	elif request.method.endswith("/requestApproval"):
		await client.respond(request, {"decision": "decline"})
	else:
		await client.refuse(request)


class GptSession:
	"""One conversation with GPT that keeps its context between prompts."""

	def __init__(
		self,
		client: AppServerClient,
		thread_id: str,
		source_tools: SourceTools,
		reasoning_effort: str,
	) -> None:
		self._client = client
		self._thread_id = thread_id
		self._source_tools = source_tools
		self._reasoning_effort = reasoning_effort
		self._turn_id: str | None = None
		self._was_interrupted = False

	async def send(self, prompt: str, images: Sequence[PromptImage] = ()) -> None:
		"""Start a turn with a prompt and the images it refers to, in order."""
		self._was_interrupted = False
		self._turn_id = await start_turn(
			self._client, self._thread_id, prompt, images, self._reasoning_effort
		)

	async def receive(self) -> AsyncIterator[ProviderEvent]:
		"""Yield the events of the current turn, ending with TurnEnded."""
		turn_id = self._turn_id
		forbidden_item_type: str | None = None

		while turn_id is not None:
			try:
				message = await self._client.receive()
				if isinstance(message, ServerRequest):
					await answer_server_request(self._client, message, self._source_tools)
					continue

				# Stop the turn the moment the model starts anything other than drawing.
				started_item_type = find_forbidden_item(message)
				if started_item_type and forbidden_item_type is None:
					forbidden_item_type = started_item_type
					await interrupt_turn(self._client, self._thread_id, turn_id)
			except AppServerError as error:
				yield TurnEnded(was_interrupted=self._was_interrupted, error_message=str(error))
				return

			# Show the caption of a step as soon as the model starts the call that carries it.
			reasoning = read_started_reasoning(message, turn_id)
			if reasoning:
				yield ReasoningProgress(text=reasoning)

			turn = read_completed_turn(message, turn_id)
			if turn is None:
				continue

			# Report a turn this client stopped as a failure, not as the director's interrupt.
			if forbidden_item_type is not None:
				error_message = describe_forbidden_item(forbidden_item_type)
				yield TurnEnded(was_interrupted=False, error_message=error_message)
				return

			has_failed = turn.get("status") == "failed"
			yield TurnEnded(
				was_interrupted=self._was_interrupted or turn.get("status") == "interrupted",
				error_message=describe_turn_error(turn.get("error")) if has_failed else None,
			)
			return

	async def interrupt(self) -> None:
		"""Cut the current turn short."""
		if self._turn_id is None:
			return
		self._was_interrupted = True
		await interrupt_turn(self._client, self._thread_id, self._turn_id)


async def start_turn(
	client: AppServerClient,
	thread_id: str,
	prompt: str,
	images: Sequence[PromptImage],
	reasoning_effort: str,
) -> str:
	"""Start a turn and return its id.

	Raises:
		ModelCallError: Codex refused the turn or went away.
	"""
	try:
		result = await client.request(
			"turn/start",
			{
				"threadId": thread_id,
				"input": build_turn_input(prompt, images),
				"effort": reasoning_effort,
			},
		)
	except AppServerError as error:
		raise ModelCallError(str(error)) from error
	return str(result.get("turn", {}).get("id"))


def read_started_reasoning(message: ServerNotification, turn_id: str | None) -> str | None:
	"""Return the Step Reasoning of a source tool call that a notification says has started."""
	if message.method != "item/started" or message.params.get("turnId") != turn_id:
		return None

	item = message.params.get("item")
	if not isinstance(item, dict) or item.get("type") != "dynamicToolCall":
		return None
	arguments = item.get("arguments")
	reasoning = arguments.get(design_note_field) if isinstance(arguments, dict) else None
	return reasoning if isinstance(reasoning, str) else None


def read_completed_turn(message: ServerNotification, turn_id: str | None) -> dict[str, Any] | None:
	"""Return the turn a notification says has ended, when it is the one being waited for."""
	if message.method != "turn/completed":
		return None
	turn = message.params.get("turn")
	return turn if isinstance(turn, dict) and turn.get("id") == turn_id else None


class GptProvider:
	"""Opens GPT conversations that can only call the two source tools."""

	def __init__(
		self, program: Sequence[str], working_directory: Path, reasoning_effort: str
	) -> None:
		"""Set up the provider.

		Args:
			program: The Codex program as a name on the path or a full path, then any
				arguments that must come before its own.
			working_directory: An empty folder for Codex to run in.
			reasoning_effort: How long GPT thinks before each answer: low, medium, or high.
		"""
		self._program = list(program)
		self._working_directory = working_directory
		self._reasoning_effort = reasoning_effort

	def _build_command(self) -> list[str]:
		"""Return the command that starts Codex app-server with nothing of Codex left on.

		Raises:
			ModelCallError: Codex is not installed.
		"""
		program_path = shutil.which(self._program[0])
		if program_path is None:
			raise ModelCallError(not_installed_message)

		command = [program_path, *self._program[1:], "app-server"]
		for setting in isolation_settings:
			command += ["-c", setting]
		for feature in disabled_features:
			command += ["--disable", feature]
		return command

	@asynccontextmanager
	async def _open_thread(
		self, system_prompt: str, model: str, tool_specs: Sequence[SourceToolSpec]
	) -> AsyncIterator[tuple[AppServerClient, str]]:
		"""Start Codex and a thread in it, and stop Codex when the caller is done.

		Args:
			system_prompt: Instructions that replace the ones Codex gives a coding agent.
			model: Id of the GPT model.
			tool_specs: The tools the model may call, which this client carries out.

		Yields:
			The client and the id of the thread.

		Raises:
			ModelCallError: Codex is not installed, is not signed in, or refused the thread.
		"""
		# Give Codex an empty folder of its own, so it has nothing of the repo around it.
		self._working_directory.mkdir(parents=True, exist_ok=True)
		command = self._build_command()

		try:
			client = await AppServerClient.start(command, str(self._working_directory))
		except AppServerError as error:
			raise ModelCallError(str(error)) from error

		try:
			try:
				thread_id = await self._start_thread(client, system_prompt, model, tool_specs)
			except AppServerError as error:
				raise ModelCallError(str(error)) from error
			yield client, thread_id
		finally:
			await client.close()

	async def _start_thread(
		self,
		client: AppServerClient,
		system_prompt: str,
		model: str,
		tool_specs: Sequence[SourceToolSpec],
	) -> str:
		"""Greet Codex, check the login, and start a thread that can only call the given tools."""
		# Ask for the experimental interface, which the tools of this client are part of.
		await client.request(
			"initialize",
			{
				"clientInfo": {
					"name": client_name,
					"title": client_title,
					"version": client_version,
				},
				"capabilities": {"experimentalApi": True, "requestAttestation": False},
			},
		)
		await client.notify("initialized")

		# Stop early when nobody is signed in, and say so when calls would be billed to an API key.
		account_state = await client.request("account/read", {"refreshToken": False})
		account = account_state.get("account")
		if account is None and account_state.get("requiresOpenaiAuth"):
			raise ModelCallError(sign_in_message)
		if isinstance(account, dict) and account.get("type") == "apiKey":
			logger.warning(
				"Codex is signed in with an API key, so GPT bills the API, not the plan."
			)

		# Switch off the tool servers of the director's own Codex setup for this thread.
		settings = (await client.request("config/read", {"includeLayers": False})).get("config")
		tool_servers = settings.get("mcp_servers") if isinstance(settings, dict) else None
		server_names = list(tool_servers) if isinstance(tool_servers, dict) else []

		thread_state = await client.request(
			"thread/start",
			{
				"model": model,
				"cwd": str(self._working_directory),
				"approvalPolicy": "never",
				"sandbox": "read-only",
				"baseInstructions": system_prompt,
				"ephemeral": True,
				"config": {f"mcp_servers.{name}.enabled": False for name in server_names},
				"dynamicTools": [
					{
						"type": "function",
						"name": spec.name,
						"description": spec.description,
						"inputSchema": spec.input_schema,
					}
					for spec in tool_specs
				],
			},
		)
		return str(thread_state.get("thread", {}).get("id"))

	@asynccontextmanager
	async def open_session(
		self, *, system_prompt: str, model: str, source_tools: SourceTools
	) -> AsyncIterator[ModelSession]:
		"""Open a conversation that lasts for one generation."""
		async with self._open_thread(system_prompt, model, source_tool_specs) as (
			client,
			thread_id,
		):
			yield GptSession(client, thread_id, source_tools, self._reasoning_effort)

	async def complete(self, *, system_prompt: str, prompt: str, model: str) -> str:
		"""Return the answer to one prompt, with no tools and no memory."""
		async with self._open_thread(system_prompt, model, ()) as (client, thread_id):
			turn_id = await start_turn(client, thread_id, prompt, (), self._reasoning_effort)

			# Keep the text of the newest message, which is the answer once the turn ends.
			answer = ""
			while True:
				try:
					message = await client.receive()
					if isinstance(message, ServerRequest):
						await answer_server_request(client, message, None)
						continue
				except AppServerError as error:
					raise ModelCallError(str(error)) from error

				# Give up the moment the model starts anything other than answering.
				forbidden_item_type = find_forbidden_item(message)
				if forbidden_item_type:
					raise ModelCallError(describe_forbidden_item(forbidden_item_type))

				item = message.params.get("item")
				is_message = isinstance(item, dict) and item.get("type") == "agentMessage"
				if message.method == "item/completed" and is_message:
					answer = str(item.get("text") or "")

				turn = read_completed_turn(message, turn_id)
				if turn is not None:
					if turn.get("status") == "failed":
						raise ModelCallError(describe_turn_error(turn.get("error")))
					return answer
