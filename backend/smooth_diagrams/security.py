"""Keep other websites from driving the local server through the director's browser."""

import re

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

safe_methods = {"GET", "HEAD", "OPTIONS"}


class OriginGuard:
	"""Refuse state-changing requests and WebSockets that come from an unknown origin.

	Browsers attach an Origin header to both, and CORS alone does not cover WebSockets
	or simple cross-site form posts. Requests without the header come from local tools.
	"""

	def __init__(self, app: ASGIApp, allowed_origin_pattern: str) -> None:
		self._app = app
		self._allowed_origin = re.compile(allowed_origin_pattern)

	async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
		if scope["type"] not in ("http", "websocket"):
			await self._app(scope, receive, send)
			return

		origin = Headers(scope=scope).get("origin")
		changes_state = scope["type"] == "websocket" or scope["method"] not in safe_methods
		is_allowed = origin is None or self._allowed_origin.fullmatch(origin) is not None
		if is_allowed or not changes_state:
			await self._app(scope, receive, send)
			return

		# Refuse in the way each connection type expects.
		if scope["type"] == "websocket":
			await send({"type": "websocket.close", "code": 1008})
		else:
			response = PlainTextResponse("Origin not allowed", status_code=403)
			await response(scope, receive, send)
