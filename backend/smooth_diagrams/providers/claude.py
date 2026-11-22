"""Claude through the Claude Agent SDK, signed in with this machine's Claude plan login."""

import base64
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
	ClaudeAgentOptions,
	ClaudeSDKClient,
	McpSdkServerConfig,
	ResultMessage,
	StreamEvent,
	create_sdk_mcp_server,
	query,
	tool,
)

from smooth_diagrams.generation.partial_json import read_partial_string_field
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

server_name = "diagram"

# Reasons the CLI gives for a turn that was cut short on request.
interrupted_reasons = {"aborted_streaming", "aborted_tools"}

# Tool calls a single generation may make before the CLI ends it.
turn_limit = 80


def build_source_server(source_tools: SourceTools) -> McpSdkServerConfig:
	"""Return an in-process tool server that forwards the two source tools to the session."""

	def build_tool(spec: SourceToolSpec) -> Any:
		@tool(spec.name, spec.description, spec.input_schema)
		async def run_tool(arguments: dict[str, Any]) -> dict[str, Any]:
			# Answer in the shape the SDK sends back to the model.
			reply = await call_source_tool(source_tools, spec.name, arguments)
			return {"content": [{"type": "text", "text": reply.text}], "is_error": reply.is_error}

		return run_tool

	return create_sdk_mcp_server(
		name=server_name, tools=[build_tool(spec) for spec in source_tool_specs]
	)


def describe_result_error(result: ResultMessage) -> str:
	"""Return a message for a turn that ended in an error."""
	if result.api_error_status == 401:
		return "Claude is not signed in. Run `claude` in a terminal, sign in, and try again."
	details = result.result or "; ".join(result.errors or []) or result.subtype
	return f"Claude ended the turn with an error: {details}"


class ClaudeSession:
	"""One conversation with Claude that keeps its context between prompts."""

	def __init__(self, client: ClaudeSDKClient) -> None:
		self._client = client
		self._was_interrupted = False

	async def send(self, prompt: str, images: Sequence[PromptImage] = ()) -> None:
		"""Start a turn with a prompt and the images it refers to, in order."""
		self._was_interrupted = False
		if not images:
			await self._client.query(prompt)
			return

		# Send the text and the images as one user message.
		content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
		for image in images:
			content.append(
				{
					"type": "image",
					"source": {
						"type": "base64",
						"media_type": image.media_type,
						"data": base64.b64encode(image.data).decode("ascii"),
					},
				}
			)
		message = {
			"type": "user",
			"message": {"role": "user", "content": content},
			"parent_tool_use_id": None,
		}

		async def one_message() -> AsyncIterator[dict[str, Any]]:
			yield message

		await self._client.query(one_message())

	async def receive(self) -> AsyncIterator[ProviderEvent]:
		"""Yield the events of the current turn, ending with TurnEnded."""
		tool_inputs: dict[int, str] = {}
		last_reasoning = ""

		async for message in self._client.receive_response():
			if isinstance(message, StreamEvent):
				reasoning = read_streamed_reasoning(message.event, tool_inputs)
				if reasoning and reasoning != last_reasoning:
					last_reasoning = reasoning
					yield ReasoningProgress(text=reasoning)
			elif isinstance(message, ResultMessage):
				was_interrupted = (
					self._was_interrupted or message.terminal_reason in interrupted_reasons
				)
				error_message = describe_result_error(message) if message.is_error else None
				yield TurnEnded(was_interrupted=was_interrupted, error_message=error_message)

	async def interrupt(self) -> None:
		"""Cut the current turn short."""
		self._was_interrupted = True
		await self._client.interrupt()


def read_streamed_reasoning(event: dict[str, Any], tool_inputs: dict[int, str]) -> str | None:
	"""Return the Step Reasoning streamed so far in the tool call an event belongs to.

	Args:
		event: One raw stream event from the model.
		tool_inputs: Partial tool input JSON by content block index, updated in place.

	Returns:
		The reasoning text received so far, or None when the event carries none.
	"""
	event_type = event.get("type")
	index = event.get("index")

	if event_type == "message_start":
		tool_inputs.clear()
	elif event_type == "content_block_start":
		if event.get("content_block", {}).get("type") == "tool_use":
			tool_inputs[index] = ""
	elif event_type == "content_block_delta" and index in tool_inputs:
		delta = event.get("delta", {})
		if delta.get("type") == "input_json_delta":
			tool_inputs[index] += delta.get("partial_json", "")
			return read_partial_string_field(tool_inputs[index], design_note_field)
	return None


class ClaudeProvider:
	"""Opens Claude conversations that can only call the two source tools."""

	def __init__(self, working_directory: Path) -> None:
		self._working_directory = working_directory

	@asynccontextmanager
	async def open_session(
		self, *, system_prompt: str, model: str, source_tools: SourceTools
	) -> AsyncIterator[ModelSession]:
		"""Open a conversation that lasts for one generation."""
		# Give the CLI an empty folder of its own, so it reads nothing from the repo.
		self._working_directory.mkdir(parents=True, exist_ok=True)

		options = ClaudeAgentOptions(
			system_prompt=system_prompt,
			model=model,
			cwd=self._working_directory,
			tools=[],
			mcp_servers={server_name: build_source_server(source_tools)},
			strict_mcp_config=True,
			allowed_tools=[f"mcp__{server_name}__{spec.name}" for spec in source_tool_specs],
			setting_sources=[],
			skills=[],
			include_partial_messages=True,
			verbatim_prompts=True,
			max_turns=turn_limit,
		)
		async with ClaudeSDKClient(options) as client:
			yield ClaudeSession(client)

	async def complete(self, *, system_prompt: str, prompt: str, model: str) -> str:
		"""Return the answer to one prompt, with no tools and no memory."""
		self._working_directory.mkdir(parents=True, exist_ok=True)

		options = ClaudeAgentOptions(
			system_prompt=system_prompt,
			model=model,
			cwd=self._working_directory,
			tools=[],
			strict_mcp_config=True,
			setting_sources=[],
			skills=[],
			verbatim_prompts=True,
			max_turns=1,
		)

		# Keep the text of the answer, which the final result message repeats in full.
		answer = ""
		async for message in query(prompt=prompt, options=options):
			if isinstance(message, ResultMessage):
				if message.is_error:
					raise ModelCallError(describe_result_error(message))
				answer = message.result or ""
		return answer
