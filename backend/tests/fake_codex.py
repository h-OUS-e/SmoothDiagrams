"""A stand-in for `codex app-server`, so tests of the GPT provider need neither Codex nor a model.

It speaks the same line protocol on stdin and stdout. What a turn does is chosen by the first
word of its prompt, and everything worth checking is appended to the file FAKE_CODEX_LOG names.
"""

import json
import os
import sys
from typing import Any

thread_id = "thread_1"
log_path = os.environ["FAKE_CODEX_LOG"]
account_kind = os.environ.get("FAKE_CODEX_ACCOUNT", "chatgpt")
last_request_id = 0
turn_count = 0


def log(kind: str, value: Any) -> None:
	"""Append one record of what happened to the log file."""
	with open(log_path, "a", encoding="utf-8") as log_file:
		log_file.write(json.dumps({"kind": kind, "value": value}) + "\n")


def send(message: dict[str, Any]) -> None:
	"""Write one message as a line."""
	sys.stdout.write(json.dumps(message) + "\n")
	sys.stdout.flush()


def read() -> dict[str, Any]:
	"""Return the next message from the client, or exit when the client is gone."""
	line = sys.stdin.readline()
	if not line:
		sys.exit(0)
	return json.loads(line)


def ask(method: str, params: dict[str, Any]) -> dict[str, Any]:
	"""Send a request to the client and return its whole answer."""
	global last_request_id
	last_request_id += 1
	request_id = f"server_{last_request_id}"
	send({"id": request_id, "method": method, "params": params})
	while True:
		message = read()
		if message.get("id") == request_id:
			return message


def call_tool(turn_id: str, tool: str, arguments: Any) -> None:
	"""Announce a tool call, ask the client to run it, and log what the client answers."""
	call_id = f"call_{tool}"
	item = {"type": "dynamicToolCall", "id": call_id, "tool": tool, "arguments": arguments}
	send({"method": "item/started", "params": {"item": item, "turnId": turn_id}})
	params = {"threadId": thread_id, "turnId": turn_id, "callId": call_id, "tool": tool}
	answer = ask("item/tool/call", {**params, "arguments": arguments})
	log("tool_answer", answer.get("result"))


def complete_turn(turn_id: str, status: str = "completed", error: Any = None) -> None:
	"""Report that a turn ended."""
	turn = {"id": turn_id, "status": status, "error": error}
	send({"method": "turn/completed", "params": {"threadId": thread_id, "turn": turn}})


def run_turn(turn_id: str, prompt: str) -> None:
	"""Play the turn its prompt asks for."""
	scenario = prompt.split()[0]

	if scenario == "draw":
		# Report something from a turn that is over, which the client must not mix in.
		stale_item = {"type": "dynamicToolCall", "arguments": {"design_note": "Stale"}}
		send({"method": "item/started", "params": {"item": stale_item, "turnId": "turn_0"}})
		sys.stdout.write("this line is not JSON\n")
		call_tool(turn_id, "write_source", {"design_note": "Circle first", "source": "<svg />"})
		edits = [{"old_text": "<svg />", "new_text": "<svg><rect /></svg>"}]
		call_tool(turn_id, "edit_source", {"design_note": "Then a rect", "edits": edits})
		complete_turn(turn_id)

	elif scenario == "malformed":
		call_tool(turn_id, "write_source", {"source": "<svg />"})
		call_tool(turn_id, "edit_source", {"design_note": "No edits", "edits": [{"old_text": 1}]})
		call_tool(turn_id, "erase_source", {"design_note": "No such tool"})
		call_tool(turn_id, "write_source", "not an object")
		complete_turn(turn_id)

	elif scenario == "hold":
		# Keep the turn open until the client interrupts it.
		while True:
			message = read()
			if message.get("method") == "turn/interrupt":
				log("interrupt", message["params"])
				send({"id": message["id"], "result": {}})
				complete_turn(turn_id, status="interrupted")
				return

	elif scenario == "spawn":
		# Start an agent of Codex's own, on another thread, and go on until interrupted.
		item = {"type": "collabAgentToolCall", "id": "agent_1", "tool": "spawnAgent"}
		send({"method": "item/started", "params": {"item": item, "turnId": turn_id}})
		while True:
			message = read()
			if message.get("method") == "turn/interrupt":
				log("interrupt", message["params"])
				send({"id": message["id"], "result": {}})
				complete_turn(turn_id, status="interrupted")
				return

	elif scenario == "fail":
		error = {"message": "You have hit your limit.", "codexErrorInfo": "usageLimitExceeded"}
		complete_turn(turn_id, status="failed", error=error)

	elif scenario == "unauthorized":
		error = {"message": "401", "codexErrorInfo": "unauthorized"}
		complete_turn(turn_id, status="failed", error=error)

	elif scenario == "crash":
		sys.stderr.write("fatal: the model exploded\n")
		sys.stderr.flush()
		sys.exit(3)

	elif scenario == "approve":
		approval = ask(
			"item/fileChange/requestApproval", {"threadId": thread_id, "turnId": turn_id}
		)
		log("approval_answer", approval.get("result"))
		question = ask("item/tool/requestUserInput", {"threadId": thread_id, "turnId": turn_id})
		log("question_answer", question.get("error"))
		complete_turn(turn_id)

	elif scenario == "answer":
		for text in ("Thinking about it.", "Because it is calm."):
			item = {"type": "agentMessage", "id": "message_1", "text": text}
			send({"method": "item/completed", "params": {"item": item, "turnId": turn_id}})
		complete_turn(turn_id)

	else:
		complete_turn(turn_id)


def handle(message: dict[str, Any]) -> None:
	"""Answer one request from the client."""
	global turn_count
	method = message.get("method")
	params = message.get("params", {})

	if method == "initialize":
		log("argv", sys.argv[1:])
		log("initialize", params)
		send({"id": message["id"], "result": {"userAgent": "fake"}})
	elif method == "account/read":
		accounts = {
			"chatgpt": {"type": "chatgpt", "planType": "plus"},
			"api_key": {"type": "apiKey"},
			"none": None,
		}
		result = {"account": accounts[account_kind], "requiresOpenaiAuth": True}
		send({"id": message["id"], "result": result})
	elif method == "config/read":
		config = {"model": "gpt", "mcp_servers": {"notes": {"command": "notes"}}}
		send({"id": message["id"], "result": {"config": config}})
	elif method == "thread/start":
		log("thread_start", params)
		if params.get("model") == "refused":
			send({"id": message["id"], "error": {"code": -32600, "message": "unknown model"}})
		else:
			send({"id": message["id"], "result": {"thread": {"id": thread_id}}})
	elif method == "turn/start":
		log("turn_start", params)
		turn_count += 1
		turn_id = f"turn_{turn_count}"
		send({"id": message["id"], "result": {"turn": {"id": turn_id, "status": "inProgress"}}})
		send({"method": "turn/started", "params": {"threadId": thread_id, "turn": {"id": turn_id}}})
		run_turn(turn_id, params["input"][0]["text"])
	elif method == "turn/interrupt":
		send({"id": message["id"], "error": {"code": -32600, "message": "no turn is running"}})
	elif method == "initialized":
		log("initialized", True)


while True:
	handle(read())
