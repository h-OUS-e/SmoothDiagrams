"""Tests for the GPT provider, run against a stand-in for Codex app-server."""

import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from smooth_diagrams.generation.source_edits import SourceEdit
from smooth_diagrams.model_catalog import ModelVendor
from smooth_diagrams.providers.base import (
	ModelCallError,
	ModelSession,
	PromptImage,
	ProviderEvent,
	ReasoningProgress,
	SourceTools,
	ToolReply,
	TurnEnded,
)
from smooth_diagrams.providers.gpt import GptProvider, not_installed_message, sign_in_message
from smooth_diagrams.providers.routing import RoutingProvider

fake_codex_path = Path(__file__).parent / "fake_codex.py"
system_prompt = "You draw diagrams as code."


class RecordingTools:
	"""Source tools that remember how they were called and answer like a saved step."""

	def __init__(self) -> None:
		self.calls: list[tuple[str, str, Any]] = []

	async def write_source(self, step_reasoning: str, source: str) -> ToolReply:
		self.calls.append(("write_source", step_reasoning, source))
		return ToolReply(f"Saved as step {len(self.calls)}.")

	async def edit_source(self, step_reasoning: str, edits: list[SourceEdit]) -> ToolReply:
		self.calls.append(("edit_source", step_reasoning, edits))
		return ToolReply("The edit did not render.", is_error=True)


@pytest.fixture
def log_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	"""Return the file the stand-in logs to, and point the stand-in at it."""
	path = tmp_path / "fake_codex.log"
	monkeypatch.setenv("FAKE_CODEX_LOG", str(path))
	return path


@pytest.fixture
def provider(tmp_path: Path, log_path: Path) -> GptProvider:
	"""Return a provider that runs the stand-in instead of Codex."""
	program = [sys.executable, str(fake_codex_path)]
	return GptProvider(program, tmp_path / "codex_workspace", reasoning_effort="low")


def read_log(log_path: Path, kind: str) -> list[Any]:
	"""Return what the stand-in logged under one kind, in order."""
	records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
	return [record["value"] for record in records if record["kind"] == kind]


@asynccontextmanager
async def open_session(
	provider: GptProvider, tools: SourceTools | None = None, model: str = "gpt-5.6-luna"
) -> AsyncIterator[ModelSession]:
	"""Open a session with the test's system prompt."""
	async with provider.open_session(
		system_prompt=system_prompt, model=model, source_tools=tools or RecordingTools()
	) as session:
		yield session


async def run_turn(session: ModelSession, prompt: str) -> list[ProviderEvent]:
	"""Send a prompt and return every event of its turn."""
	await session.send(prompt)
	return [event async for event in session.receive()]


# ---------------------------------------------------------------------------
# Turns
# ---------------------------------------------------------------------------


async def test_tool_calls_reach_the_source_tools_and_their_replies_reach_the_model(
	provider: GptProvider, log_path: Path
) -> None:
	tools = RecordingTools()
	async with open_session(provider, tools) as session:
		events = await run_turn(session, "draw a diagram")

	# The caption of each step shows as its call starts; one of another turn is left out.
	assert events == [
		ReasoningProgress("Circle first"),
		ReasoningProgress("Then a rect"),
		TurnEnded(was_interrupted=False),
	]
	assert tools.calls == [
		("write_source", "Circle first", "<svg />"),
		("edit_source", "Then a rect", [SourceEdit("<svg />", "<svg><rect /></svg>")]),
	]
	assert read_log(log_path, "tool_answer") == [
		{"contentItems": [{"type": "inputText", "text": "Saved as step 1."}], "success": True},
		{
			"contentItems": [{"type": "inputText", "text": "The edit did not render."}],
			"success": False,
		},
	]


async def test_thread_gives_the_model_nothing_of_codex_but_the_source_tools(
	provider: GptProvider, log_path: Path, tmp_path: Path
) -> None:
	async with open_session(provider) as session:
		await run_turn(session, "nothing to do")

	# Codex starts with its own tools and the director's setup switched off.
	[arguments] = read_log(log_path, "argv")
	assert arguments[0] == "app-server"
	assert "project_doc_max_bytes=0" in arguments
	assert 'web_search="disabled"' in arguments
	for feature in ("shell_tool", "unified_exec", "plugins", "multi_agent"):
		assert arguments[arguments.index(feature) - 1] == "--disable"
	assert read_log(log_path, "initialize")[0]["capabilities"]["experimentalApi"] is True
	assert read_log(log_path, "initialized") == [True]

	# The thread replaces the coding instructions, may change nothing, and never asks.
	[thread] = read_log(log_path, "thread_start")
	assert thread["model"] == "gpt-5.6-luna"
	assert thread["baseInstructions"] == system_prompt
	assert thread["sandbox"] == "read-only"
	assert thread["approvalPolicy"] == "never"
	assert thread["ephemeral"] is True
	assert thread["cwd"] == str(tmp_path / "codex_workspace")
	assert thread["config"] == {"mcp_servers.notes.enabled": False}
	assert [tool["name"] for tool in thread["dynamicTools"]] == ["write_source", "edit_source"]
	assert "design_note" in thread["dynamicTools"][0]["inputSchema"]["required"]

	assert read_log(log_path, "turn_start")[0]["effort"] == "low"


async def test_images_are_sent_with_the_prompt_as_data_addresses(
	provider: GptProvider, log_path: Path
) -> None:
	async with open_session(provider) as session:
		await session.send("look at this", [PromptImage("image/png", b"\x89PNG")])
		[event async for event in session.receive()]

	[turn] = read_log(log_path, "turn_start")
	assert turn["input"] == [
		{"type": "text", "text": "look at this", "text_elements": []},
		{"type": "image", "url": "data:image/png;base64,iVBORw=="},
	]


async def test_interrupt_ends_the_turn_as_interrupted(
	provider: GptProvider, log_path: Path
) -> None:
	async with open_session(provider) as session:
		await session.send("hold on")
		await session.interrupt()
		events = [event async for event in session.receive()]

		# The conversation goes on after an interrupt.
		later_events = await run_turn(session, "nothing to do")

	assert events == [TurnEnded(was_interrupted=True)]
	assert read_log(log_path, "interrupt") == [{"threadId": "thread_1", "turnId": "turn_1"}]
	assert later_events == [TurnEnded(was_interrupted=False)]


async def test_interrupt_after_the_turn_ended_is_harmless(provider: GptProvider) -> None:
	async with open_session(provider) as session:
		await run_turn(session, "nothing to do")
		await session.interrupt()


async def test_malformed_tool_calls_are_answered_with_errors(
	provider: GptProvider, log_path: Path
) -> None:
	tools = RecordingTools()
	async with open_session(provider, tools) as session:
		events = await run_turn(session, "malformed calls")

	assert tools.calls == []
	answers = read_log(log_path, "tool_answer")
	assert [answer["success"] for answer in answers] == [False, False, False, False]
	assert [answer["contentItems"][0]["text"] for answer in answers] == [
		"design_note and source must be strings.",
		"Every edit needs old_text and new_text.",
		"There is no tool named erase_source.",
		"The arguments must be an object.",
	]
	assert events[-1] == TurnEnded(was_interrupted=False)


async def test_requests_codex_makes_on_its_own_are_turned_down(
	provider: GptProvider, log_path: Path
) -> None:
	async with open_session(provider) as session:
		events = await run_turn(session, "approve this")

	assert read_log(log_path, "approval_answer") == [{"decision": "decline"}]
	assert read_log(log_path, "question_answer")[0]["code"] == -32601
	assert events == [TurnEnded(was_interrupted=False)]


async def test_turn_that_starts_an_agent_of_its_own_is_stopped_as_a_failure(
	provider: GptProvider, log_path: Path
) -> None:
	async with open_session(provider) as session:
		[event] = await run_turn(session, "spawn an agent")

	# The provider interrupts the turn itself, and does not pass it off as the director's doing.
	assert read_log(log_path, "interrupt") == [{"threadId": "thread_1", "turnId": "turn_1"}]
	assert isinstance(event, TurnEnded)
	assert event.was_interrupted is False
	assert "something other than drawing (collabAgentToolCall)" in (event.error_message or "")


async def test_one_off_prompt_that_starts_an_agent_of_its_own_is_given_up(
	provider: GptProvider,
) -> None:
	with pytest.raises(ModelCallError, match="something other than drawing"):
		await provider.complete(system_prompt="", prompt="spawn an agent", model="gpt-5.6-luna")


# ---------------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------------


async def test_failed_turn_reports_its_reason(provider: GptProvider) -> None:
	async with open_session(provider) as session:
		[limit_reached] = await run_turn(session, "fail now")
		[signed_out] = await run_turn(session, "unauthorized")

	assert limit_reached == TurnEnded(
		was_interrupted=False,
		error_message="The usage limit of your ChatGPT plan is reached: You have hit your limit.",
	)
	assert signed_out.error_message == sign_in_message


async def test_codex_that_stops_mid_turn_ends_the_turn_with_what_it_said(
	provider: GptProvider,
) -> None:
	async with open_session(provider) as session:
		[event] = await run_turn(session, "crash now")

	assert isinstance(event, TurnEnded)
	assert event.error_message == "Codex stopped unexpectedly. fatal: the model exploded"


async def test_missing_login_is_reported_before_any_turn(
	provider: GptProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
	monkeypatch.setenv("FAKE_CODEX_ACCOUNT", "none")

	with pytest.raises(ModelCallError) as raised:
		async with open_session(provider):
			pass
	assert str(raised.value) == sign_in_message


async def test_api_key_login_is_allowed_but_warned_about(
	provider: GptProvider, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
	monkeypatch.setenv("FAKE_CODEX_ACCOUNT", "api_key")

	async with open_session(provider) as session:
		await run_turn(session, "nothing to do")

	assert "bills the API" in caplog.text


async def test_thread_that_codex_refuses_is_reported(provider: GptProvider) -> None:
	with pytest.raises(ModelCallError, match="unknown model"):
		async with open_session(provider, model="refused"):
			pass


async def test_codex_that_is_not_installed_is_reported(tmp_path: Path) -> None:
	provider = GptProvider(["no_such_codex_program"], tmp_path / "workspace", "low")

	with pytest.raises(ModelCallError) as raised:
		async with open_session(provider):
			pass
	assert str(raised.value) == not_installed_message


# ---------------------------------------------------------------------------
# One-off prompts
# ---------------------------------------------------------------------------


async def test_complete_returns_the_final_message(provider: GptProvider, log_path: Path) -> None:
	answer = await provider.complete(
		system_prompt="You explain taste.", prompt="answer briefly", model="gpt-5.6-luna"
	)

	assert answer == "Because it is calm."
	[thread] = read_log(log_path, "thread_start")
	assert thread["baseInstructions"] == "You explain taste."
	assert thread["dynamicTools"] == []


async def test_complete_raises_when_the_turn_fails(provider: GptProvider) -> None:
	with pytest.raises(ModelCallError, match="usage limit"):
		await provider.complete(system_prompt="", prompt="fail now", model="gpt-5.6-luna")


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class NamedProvider:
	"""A provider that only says which vendor it stands for."""

	def __init__(self, name: str) -> None:
		self._name = name

	def open_session(self, **options: Any) -> Any:
		return f"{self._name} session for {options['model']}"

	async def complete(self, **options: Any) -> str:
		return f"{self._name} answer from {options['model']}"


async def test_each_model_runs_through_the_provider_of_its_vendor() -> None:
	router = RoutingProvider(
		{
			ModelVendor.ANTHROPIC: NamedProvider("claude"),
			ModelVendor.OPENAI: NamedProvider("gpt"),
		}
	)
	options = {"system_prompt": "", "source_tools": RecordingTools()}

	assert router.open_session(model="claude-sonnet-5-5", **options) == (
		"claude session for claude-sonnet-5-5"
	)
	assert router.open_session(model="gpt-6-astra", **options) == "gpt session for gpt-6-astra"
	answer = await router.complete(system_prompt="", prompt="why", model="gpt-5.6-sol")
	assert answer == "gpt answer from gpt-5.6-sol"

	with pytest.raises(ModelCallError, match="no model named gpt-1"):
		router.open_session(model="gpt-1", **options)
