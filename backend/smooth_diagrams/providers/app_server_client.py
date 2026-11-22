"""A client for Codex app-server: JSON messages, one per line, over the program's stdin and stdout.

The messages follow JSON-RPC without its version field. Both sides send requests, which carry
an id and get one response, and notifications, which carry none.
"""

import asyncio
import contextlib
import json
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Longest line the program may send, in bytes; a turn's final message repeats whole sources.
line_byte_limit = 64 * 1024 * 1024

# Seconds the program gets to exit on its own after its input closes.
exit_timeout = 5.0

# Lines of the program's error output kept for the message of an unexpected exit.
kept_error_line_count = 20

# JSON-RPC code for a request the receiver does not support.
method_not_found_code = -32601


class AppServerError(Exception):
	"""The program could not be started, went away, or refused a request."""


@dataclass(frozen=True)
class ServerNotification:
	"""Something the program reports without expecting an answer."""

	method: str
	params: dict[str, Any]


@dataclass(frozen=True)
class ServerRequest:
	"""Something the program asks of this client, to be answered with `respond`."""

	request_id: int | str
	method: str
	params: dict[str, Any]


ServerMessage = ServerNotification | ServerRequest


class AppServerClient:
	"""One running app-server and the conversation with it."""

	def __init__(self, process: asyncio.subprocess.Process) -> None:
		self._process = process
		self._last_request_id = 0
		self._pending_responses: dict[int, asyncio.Future[dict[str, Any]]] = {}

		# What the program sent on its own, in order; None marks that it went away.
		self._incoming: asyncio.Queue[ServerMessage | None] = asyncio.Queue()
		self._error_lines: list[str] = []
		self._read_task = asyncio.create_task(self._read_messages())
		self._error_task = asyncio.create_task(self._read_error_output())

	@classmethod
	async def start(cls, command: Sequence[str], working_directory: str) -> "AppServerClient":
		"""Start the program and return a client for it.

		Raises:
			AppServerError: The program could not be started.
		"""
		try:
			process = await asyncio.create_subprocess_exec(
				*command,
				cwd=working_directory,
				stdin=asyncio.subprocess.PIPE,
				stdout=asyncio.subprocess.PIPE,
				stderr=asyncio.subprocess.PIPE,
				limit=line_byte_limit,
			)
		except OSError as error:
			raise AppServerError(f"Codex could not be started: {error}") from error
		return cls(process)

	# -----------------------------------------------------------------------
	# Sending
	# -----------------------------------------------------------------------

	async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
		"""Send a request and return its result.

		Raises:
			AppServerError: The program refused the request or went away before answering.
		"""
		self._last_request_id += 1
		request_id = self._last_request_id
		response: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
		self._pending_responses[request_id] = response

		try:
			await self._send({"id": request_id, "method": method, "params": params})
			return await response
		finally:
			self._pending_responses.pop(request_id, None)

	async def notify(self, method: str) -> None:
		"""Send a notification, which gets no answer."""
		await self._send({"method": method})

	async def respond(self, request: ServerRequest, result: dict[str, Any]) -> None:
		"""Answer a request the program made."""
		await self._send({"id": request.request_id, "result": result})

	async def refuse(self, request: ServerRequest) -> None:
		"""Answer a request the program made by saying this client does not support it."""
		error = {"code": method_not_found_code, "message": f"{request.method} is not supported."}
		await self._send({"id": request.request_id, "error": error})

	async def _send(self, message: dict[str, Any]) -> None:
		"""Write one message as a line."""
		stdin = self._process.stdin
		if stdin is None or stdin.is_closing():
			raise AppServerError(self._describe_exit())
		try:
			stdin.write(json.dumps(message).encode("utf-8") + b"\n")
			await stdin.drain()
		except OSError as error:
			raise AppServerError(self._describe_exit()) from error

	# -----------------------------------------------------------------------
	# Receiving
	# -----------------------------------------------------------------------

	async def receive(self) -> ServerMessage:
		"""Return the next notification or request from the program.

		Raises:
			AppServerError: The program went away.
		"""
		message = await self._incoming.get()
		if message is None:
			# Leave the mark in place, so every later call fails the same way.
			self._incoming.put_nowait(None)
			raise AppServerError(self._describe_exit())
		return message

	async def _read_messages(self) -> None:
		"""Sort every line the program writes into responses and its own messages."""
		stdout = self._process.stdout
		assert stdout is not None
		try:
			while line := await stdout.readline():
				try:
					message = json.loads(line)
				except ValueError:
					logger.warning("Codex wrote a line that is not JSON: %r", line[:200])
					continue
				if isinstance(message, dict):
					self._dispatch(message)
		except (OSError, ValueError) as error:
			logger.warning("Reading from Codex failed: %s", error)
		finally:
			# Fail everything that still waits, now that no answer can arrive.
			await asyncio.wait({self._error_task}, timeout=exit_timeout)
			for response in self._pending_responses.values():
				if not response.done():
					response.set_exception(AppServerError(self._describe_exit()))
			self._incoming.put_nowait(None)

	def _dispatch(self, message: dict[str, Any]) -> None:
		"""Hand one message to whoever waits for it."""
		method = message.get("method")
		params = message.get("params")
		params = params if isinstance(params, dict) else {}

		if isinstance(method, str) and "id" in message:
			self._incoming.put_nowait(ServerRequest(message["id"], method, params))
		elif isinstance(method, str):
			self._incoming.put_nowait(ServerNotification(method, params))
		else:
			response = self._pending_responses.get(message.get("id"))
			if response is None or response.done():
				return
			if "error" in message:
				details = message["error"]
				text = details.get("message") if isinstance(details, dict) else str(details)
				response.set_exception(AppServerError(f"Codex refused a request: {text}"))
			else:
				result = message.get("result")
				response.set_result(result if isinstance(result, dict) else {})

	async def _read_error_output(self) -> None:
		"""Keep the last lines of the program's error output, which explain an exit."""
		stderr = self._process.stderr
		assert stderr is not None
		with contextlib.suppress(OSError, ValueError):
			while line := await stderr.readline():
				self._error_lines.append(line.decode("utf-8", errors="replace").rstrip())
				del self._error_lines[:-kept_error_line_count]

	def _describe_exit(self) -> str:
		"""Return a message for a program that went away, with what it last complained about."""
		details = " ".join(line for line in self._error_lines if line).strip()
		return f"Codex stopped unexpectedly. {details}".strip()

	# -----------------------------------------------------------------------
	# Stopping
	# -----------------------------------------------------------------------

	async def close(self) -> None:
		"""Stop the program: ask by closing its input, and end it by force if it stays."""
		stdin = self._process.stdin
		if stdin is not None and not stdin.is_closing():
			stdin.close()

		try:
			await asyncio.wait_for(self._process.wait(), exit_timeout)
		except TimeoutError:
			await self._end_by_force()
		await asyncio.gather(self._read_task, self._error_task, return_exceptions=True)

	async def _end_by_force(self) -> None:
		"""End the program and everything it started."""
		# On Windows the program is started through a script, whose children outlive it.
		if sys.platform == "win32":
			killer = await asyncio.create_subprocess_exec(
				"taskkill",
				"/PID",
				str(self._process.pid),
				"/T",
				"/F",
				stdout=asyncio.subprocess.DEVNULL,
				stderr=asyncio.subprocess.DEVNULL,
			)
			await killer.wait()
		else:
			with contextlib.suppress(ProcessLookupError):
				self._process.kill()
		await self._process.wait()
