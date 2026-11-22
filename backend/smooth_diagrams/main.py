"""The local server: storage and model calls for the SmoothDiagrams frontend."""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from smooth_diagrams.database import queries
from smooth_diagrams.database.engine import create_engine, create_session_factory, run_migrations
from smooth_diagrams.providers.base import ModelProvider
from smooth_diagrams.providers.claude import ClaudeProvider
from smooth_diagrams.routes import generations, models, nodes, projects
from smooth_diagrams.security import OriginGuard
from smooth_diagrams.settings import Settings, backend_directory, get_settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, provider: ModelProvider | None = None) -> FastAPI:
	"""Return the server app.

	Args:
		settings: Settings to use instead of the ones read from the environment.
		provider: Model provider to use instead of Claude, such as a scripted one in tests.

	Returns:
		The FastAPI app, which migrates and opens the database when it starts.
	"""
	app_settings = settings or get_settings()

	@asynccontextmanager
	async def lifespan(app: FastAPI) -> AsyncIterator[None]:
		# Bring the schema up to date before anything reads the database.
		await asyncio.to_thread(run_migrations, app_settings.database_url)
		engine = create_engine(app_settings.database_url)

		app.state.settings = app_settings
		app.state.session_factory = create_session_factory(engine)
		app.state.provider = provider or ClaudeProvider(
			backend_directory / "data" / "claude_workspace"
		)

		# Close the books on generations that a previous run left unfinished.
		async with app.state.session_factory() as session:
			await queries.mark_interrupted_nodes(session)

		if os.environ.get("ANTHROPIC_API_KEY"):
			logger.warning(
				"ANTHROPIC_API_KEY is set, so Claude will bill the API instead of the plan login."
			)

		yield
		await engine.dispose()

	app = FastAPI(title="SmoothDiagrams", lifespan=lifespan)
	app.add_middleware(
		CORSMiddleware,
		allow_origin_regex=app_settings.frontend_origin_pattern,
		allow_methods=["GET", "POST", "PATCH", "DELETE"],
		allow_headers=["content-type"],
	)
	app.add_middleware(OriginGuard, allowed_origin_pattern=app_settings.frontend_origin_pattern)

	app.include_router(projects.router)
	app.include_router(nodes.router)
	app.include_router(generations.router)
	app.include_router(models.router)
	return app


app = create_app()
