"""Tests for a generation run over its WebSocket, with a scripted model."""

import asyncio
import time
from typing import Any

from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from smooth_diagrams.generation.source_edits import SourceEdit
from smooth_diagrams.providers.base import SourceTools
from tests.scripted_provider import ScriptedProvider

rendered_svg = '<svg viewBox="0 0 4 3"></svg>'
source_a = "<svg><circle /></svg>"
source_b = "<svg><circle /><rect /></svg>"
source_c = "<svg><circle /><path /></svg>"


class Director:
	"""Plays the frontend's part of a generation: renders steps and sends commands."""

	def __init__(self, websocket: WebSocketTestSession, piece_id: str, **start_fields: Any) -> None:
		self._websocket = websocket
		self.events: list[dict[str, Any]] = []
		websocket.send_json(
			{"type": "start", "piece_id": piece_id, "prompt": "Draw a diagram", **start_fields}
		)

	def receive(self) -> dict[str, Any]:
		"""Return the next event from the server."""
		event = self._websocket.receive_json()
		self.events.append(event)
		return event

	def receive_until(self, event_type: str) -> dict[str, Any]:
		"""Return the next event of one type, answering proposed steps on the way."""
		while True:
			event = self.receive()
			if event["type"] == event_type:
				return event
			if event["type"] == "step_proposed":
				self.report_rendered(event)

	def report_rendered(self, proposed: dict[str, Any]) -> None:
		"""Tell the server a proposed step rendered."""
		self.send(
			type="step_outcome",
			step_token=proposed["step_token"],
			ok=True,
			render_svg=rendered_svg,
		)

	def report_failed(self, proposed: dict[str, Any], message: str) -> None:
		"""Tell the server a proposed step did not render."""
		self.send(type="step_outcome", step_token=proposed["step_token"], ok=False, message=message)

	def send(self, **command: Any) -> None:
		"""Send one command to the server."""
		self._websocket.send_json(command)

	def event_types(self) -> list[str]:
		"""Return the types of every event received so far."""
		return [event["type"] for event in self.events]


def create_piece(client: TestClient) -> str:
	"""Create a project and return the id of its first piece."""
	return client.post("/projects", json={"name": "Postcards"}).json()["pieces"][0]["id"]


async def wait_for_interrupt(source_tools: SourceTools) -> None:
	"""Stand in for a model that keeps working until it is interrupted."""
	await asyncio.Event().wait()


def test_steps_are_saved_as_they_render(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	async def turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("Circle first", source_a)
		await source_tools.edit_source("Then a rect", [SourceEdit("</svg>", "<rect /></svg>")])

	scripted_provider.turns.append(turn)
	piece_id = create_piece(client)

	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, piece_id)
		ended = director.receive_until("generation_ended")

	assert ended["status"] == "finished"
	assert director.event_types() == [
		"node_created",
		"step_proposed",
		"step_saved",
		"step_proposed",
		"step_saved",
		"generation_ended",
	]

	node = client.get(f"/nodes/{director.events[0]['node']['id']}").json()
	assert node["status"] == "finished"
	assert [step["source"] for step in node["steps"]] == [source_a, source_b]
	assert [step["step_reasoning"] for step in node["steps"]] == ["Circle first", "Then a rect"]

	[summary] = client.get(f"/pieces/{piece_id}").json()["nodes"]
	assert summary["step_count"] == 2
	assert summary["render_svg"] == rendered_svg
	assert client.get("/projects").json()[0]["cover_svg"] == rendered_svg


def test_failed_step_is_repaired(client: TestClient, scripted_provider: ScriptedProvider) -> None:
	replies = []

	async def turn(source_tools: SourceTools) -> None:
		replies.append(await source_tools.write_source("Broken", "<svg><circle></svg>"))
		replies.append(await source_tools.write_source("Fixed", source_a))

	scripted_provider.turns.append(turn)

	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, create_piece(client))
		director.receive()
		director.report_failed(director.receive(), "Unclosed element (line 1)")
		ended = director.receive_until("generation_ended")

	assert ended["status"] == "finished"
	assert replies[0].is_error and "Unclosed element" in replies[0].text
	assert not replies[1].is_error
	assert director.event_types().count("step_saved") == 1
	assert director.event_types().count("step_failed") == 1


def test_edit_that_matches_nothing_fails_without_a_proposal(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	replies = []

	async def turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("Circle first", source_a)
		replies.append(await source_tools.edit_source("Miss", [SourceEdit("<ellipse />", "")]))

	scripted_provider.turns.append(turn)

	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, create_piece(client))
		director.receive_until("generation_ended")

	assert replies[0].is_error and "was not found" in replies[0].text
	assert director.event_types().count("step_proposed") == 1


def test_generation_fails_after_too_many_failed_attempts(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	async def turn(source_tools: SourceTools) -> None:
		for attempt in range(5):
			await source_tools.edit_source(f"Miss {attempt}", [SourceEdit("<ellipse />", "")])

	scripted_provider.turns.append(turn)

	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, create_piece(client))
		ended = director.receive_until("generation_ended")

	assert ended["status"] == "failed"
	assert "3 failed attempts" in ended["message"]


def test_generation_without_steps_fails(client: TestClient) -> None:
	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, create_piece(client))
		ended = director.receive_until("generation_ended")

	assert ended["status"] == "failed"
	assert "without drawing a step" in ended["message"]


def test_rejected_step_is_removed_and_the_model_told(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	async def first_turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("Circle first", source_a)
		await source_tools.write_source("Then a rect", source_b)
		await wait_for_interrupt(source_tools)

	async def second_turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("A path instead", source_c)

	scripted_provider.turns.extend([first_turn, second_turn])

	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, create_piece(client))
		director.receive_until("step_saved")
		rejected_step = director.receive_until("step_saved")["step"]
		director.send(type="reject_step", reason="Too boxy")
		assert director.receive_until("step_rejected")["step_id"] == rejected_step["id"]
		ended = director.receive_until("generation_ended")

	assert ended["status"] == "finished"

	# The model is told what was rejected and gets the source from before that step.
	reject_prompt = scripted_provider.prompts[1]
	assert "Then a rect" in reject_prompt
	assert "Too boxy" in reject_prompt
	assert source_a in reject_prompt and source_b not in reject_prompt

	node = client.get(f"/nodes/{director.events[0]['node']['id']}").json()
	assert [(step["source"], step["is_rejected"]) for step in node["steps"]] == [
		(source_a, False),
		(source_b, True),
		(source_c, False),
	]
	assert node["steps"][1]["rejection_reason"] == "Too boxy"


def test_pause_holds_the_work_until_resume(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	replies = []

	async def first_turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("Circle first", source_a)
		await asyncio.sleep(0.3)
		replies.append(await source_tools.write_source("Then a rect", source_b))

	async def second_turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("Then a rect", source_b)

	scripted_provider.turns.extend([first_turn, second_turn])

	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, create_piece(client))
		director.receive_until("step_saved")
		director.send(type="pause")
		director.receive_until("paused")

		# Give the scripted model time to try its next step while paused.
		time.sleep(0.6)
		assert replies[0].is_error and "paused" in replies[0].text
		assert len(scripted_provider.prompts) == 1

		director.send(type="resume")
		director.receive_until("resumed")
		ended = director.receive_until("generation_ended")

	assert ended["status"] == "finished"
	assert "resumed" in scripted_provider.prompts[1]
	assert director.event_types().count("step_saved") == 2


def test_redirect_interrupts_and_sends_the_new_direction(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	async def first_turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("Circle first", source_a)
		await wait_for_interrupt(source_tools)

	async def second_turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("A path, as asked", source_c)

	scripted_provider.turns.extend([first_turn, second_turn])

	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, create_piece(client))
		director.receive_until("step_saved")
		director.send(type="redirect", prompt="Use a path, not a rect")
		ended = director.receive_until("generation_ended")

	assert ended["status"] == "finished"
	assert "Use a path, not a rect" in scripted_provider.prompts[1]
	assert source_a in scripted_provider.prompts[1]


def test_stop_keeps_the_steps_saved_so_far(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	async def turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("Circle first", source_a)
		await wait_for_interrupt(source_tools)

	scripted_provider.turns.append(turn)

	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, create_piece(client))
		director.receive_until("step_saved")
		director.send(type="stop")
		ended = director.receive_until("generation_ended")

	assert ended["status"] == "stopped"
	node = client.get(f"/nodes/{director.events[0]['node']['id']}").json()
	assert node["status"] == "stopped"
	assert len(node["steps"]) == 1


def test_node_can_continue_from_a_step_of_another(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	async def first_turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("Circle first", source_a)
		await source_tools.write_source("Then a rect", source_b)

	async def fork_turn(source_tools: SourceTools) -> None:
		await source_tools.edit_source("A path instead", [SourceEdit("</svg>", "<path /></svg>")])

	scripted_provider.turns.extend([first_turn, fork_turn])
	piece_id = create_piece(client)

	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, piece_id)
		first_step = director.receive_until("step_saved")["step"]
		director.receive_until("generation_ended")

	# Fork from the first step, leaving the parent's second step untouched.
	with client.websocket_connect("/generations") as websocket:
		fork_director = Director(websocket, piece_id, parent_step_id=first_step["id"])
		fork_node = fork_director.receive_until("node_created")["node"]
		fork_director.receive_until("generation_ended")

	assert source_a in scripted_provider.prompts[1]
	assert fork_node["parent_node_id"] == first_step["node_id"]
	assert fork_node["parent_step"]["id"] == first_step["id"]

	stored_fork = client.get(f"/nodes/{fork_node['id']}").json()
	assert [step["source"] for step in stored_fork["steps"]] == [source_c]
	parent = client.get(f"/nodes/{first_step['node_id']}").json()
	assert [step["source"] for step in parent["steps"]] == [source_a, source_b]


def test_generation_stops_when_the_frontend_leaves(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	async def turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("Circle first", source_a)
		await wait_for_interrupt(source_tools)

	scripted_provider.turns.append(turn)

	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, create_piece(client))
		director.receive_until("step_saved")

	# Wait for the server to notice the closed socket and settle the node.
	node_id = director.events[0]["node"]["id"]
	for _ in range(40):
		if client.get(f"/nodes/{node_id}").json()["status"] != "generating":
			break
		time.sleep(0.05)
	assert client.get(f"/nodes/{node_id}").json()["status"] == "stopped"


def test_first_message_must_be_a_start_command(client: TestClient) -> None:
	with client.websocket_connect("/generations") as websocket:
		websocket.send_json({"type": "pause"})
		assert websocket.receive()["type"] == "websocket.close"
