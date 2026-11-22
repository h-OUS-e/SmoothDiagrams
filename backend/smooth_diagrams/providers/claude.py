"""Claude through the Claude Agent SDK, signed in with this machine's Claude plan login."""

from collections.abc import AsyncIterator
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
	tool,
)

from smooth_diagrams.generation.partial_json import read_partial_string_field
from smooth_diagrams.generation.source_edits import SourceEdit
from smooth_diagrams.providers.base import (
	ModelSession,
	ProviderEvent,
	ReasoningProgress,
	SourceTools,
	ToolReply,
	TurnEnded,
)

server_name = "diagram"
write_source_name = "write_source"
edit_source_name = "edit_source"

# Reasons the CLI gives for a turn that was cut short on request.
interrupted_reasons = {"aborted_streaming", "aborted_tools"}

# Tool calls a single generation may make before the CLI ends it.
turn_limit = 80

# Name the model knows a Step Reasoning by; see the note on wording in CONTEXT.md.
design_note_field = "design_note"

design_note_schema = {
	"type": "string",
	"description": (
		"Caption for the director, at most 25 words: the design choice this step makes "
		"and the alternative it passes over."
	),
}

write_source_schema = {
	"type": "object",
	"properties": {
		design_note_field: design_note_schema,
		"source": {"type": "string", "description": "The complete new source of the diagram."},
	},
	"required": [design_note_field, "source"],
}

edit_source_schema = {
	"type": "object",
	"properties": {
		design_note_field: design_note_schema,
		"edits": {
			"type": "array",
			"minItems": 1,
			"description": "Replacements applied in order, each to the result of the last.",
			"items": {
				"type": "object",
				"properties": {
					"old_text": {
						"type": "string",
						"description": "Exact text to replace. It must occur exactly once.",
					},
					"new_text": {"type": "string", "description": "Text to put in its place."},
				},
				"required": ["old_text", "new_text"],
			},
		},
	},
	"required": [design_note_field, "edits"],
}


def build_tool_result(reply: ToolReply) -> dict[str, Any]:
	"""Return a tool reply in the shape the SDK sends back to the model."""
	return {"content": [{"type": "text", "text": reply.text}], "is_error": reply.is_error}


def build_source_server(source_tools: SourceTools) -> McpSdkServerConfig:
	"""Return an in-process tool server that forwards the two source tools to the session."""

	@tool(write_source_name, "Replace the whole source as one step.", write_source_schema)
	async def write_source(arguments: dict[str, Any]) -> dict[str, Any]:
		step_reasoning = arguments.get(design_note_field)
		source = arguments.get("source")
		if not isinstance(step_reasoning, str) or not isinstance(source, str):
			return build_tool_result(ToolReply("design_note and source must be strings.", True))
		return build_tool_result(await source_tools.write_source(step_reasoning, source))

	@tool(edit_source_name, "Replace exact passages of the source as one step.", edit_source_schema)
	async def edit_source(arguments: dict[str, Any]) -> dict[str, Any]:
		step_reasoning = arguments.get(design_note_field)
		raw_edits = arguments.get("edits")
		if not isinstance(step_reasoning, str) or not isinstance(raw_edits, list):
			return build_tool_result(ToolReply("design_note and edits are required.", True))

		# Read each edit, refusing any that is not a pair of strings.
		edits: list[SourceEdit] = []
		for raw_edit in raw_edits:
			old_text = raw_edit.get("old_text") if isinstance(raw_edit, dict) else None
			new_text = raw_edit.get("new_text") if isinstance(raw_edit, dict) else None
			if not isinstance(old_text, str) or not isinstance(new_text, str):
				return build_tool_result(ToolReply("Every edit needs old_text and new_text.", True))
			edits.append(SourceEdit(old_text=old_text, new_text=new_text))

		return build_tool_result(await source_tools.edit_source(step_reasoning, edits))

	return create_sdk_mcp_server(name=server_name, tools=[write_source, edit_source])


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

	async def send(self, prompt: str) -> None:
		"""Start a turn with a prompt."""
		self._was_interrupted = False
		await self._client.query(prompt)

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
			allowed_tools=[
				f"mcp__{server_name}__{write_source_name}",
				f"mcp__{server_name}__{edit_source_name}",
			],
			setting_sources=[],
			skills=[],
			include_partial_messages=True,
			verbatim_prompts=True,
			max_turns=turn_limit,
		)
		async with ClaudeSDKClient(options) as client:
			yield ClaudeSession(client)
