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
from smooth_diagrams.model_catalog import ModelVendor
from smooth_diagrams.providers.base import ModelProvider
from smooth_diagrams.providers.claude import ClaudeProvider
from smooth_diagrams.providers.gpt import GptProvider
from smooth_diagrams.providers.routing import RoutingProvider
from smooth_diagrams.routes import (
	assets,
	exports,
	generations,
	interfaces,
	library,
	models,
	nodes,
	priors,
	projects,
	taste_priors,
)
from smooth_diagrams.security import OriginGuard
from smooth_diagrams.settings import Settings, backend_directory, get_settings
from smooth_diagrams.similarity.embedder import ClipEmbedder, ImageEmbedder
from smooth_diagrams.storage.file_store import LocalFileStore

logger = logging.getLogger(__name__)


def build_provider(settings: Settings) -> ModelProvider:
	"""Return the provider that runs each model through its vendor's own program."""
	data_directory = backend_directory / "data"
	return RoutingProvider(
		{
			ModelVendor.ANTHROPIC: ClaudeProvider(data_directory / "claude_workspace"),
			ModelVendor.OPENAI: GptProvider(
				[settings.codex_program],
				data_directory / "codex_workspace",
				settings.gpt_reasoning_effort,
			),
		}
	)


def create_app(
	settings: Settings | None = None,
	provider: ModelProvider | None = None,
	embedder: ImageEmbedder | None = None,
) -> FastAPI:
	"""Return the server app.

	Args:
		settings: Settings to use instead of the ones read from the environment.
		provider: Model provider to use for every model, such as a scripted one in tests.
		embedder: Image embedder to use instead of CLIP, such as a simple one in tests.

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
		app.state.file_store = LocalFileStore(app_settings.assets_directory)
		app.state.provider = provider or build_provider(app_settings)

		# The embedding model itself is loaded the first time the library is sorted by similarity.
		app.state.embedder = embedder or ClipEmbedder(
			app_settings.similarity_model_repository,
			app_settings.similarity_model_file,
			app_settings.similarity_model_revision,
		)

		# Close the books on generations that a previous run left unfinished.
		async with app.state.session_factory() as session:
			await queries.mark_interrupted_nodes(session)

		if os.environ.get("ANTHROPIC_API_KEY"):
			logger.warning(
				"ANTHROPIC_API_KEY is set, so Claude will bill the API instead of the plan login."
			)
		if os.environ.get("OPENAI_API_KEY"):
			logger.warning(
				"OPENAI_API_KEY is set; if Codex signs in with it, GPT bills the API, not the plan."
			)

		yield
		await engine.dispose()

	app = FastAPI(title="SmoothDiagrams", lifespan=lifespan)
	app.add_middleware(
		CORSMiddleware,
		allow_origin_regex=app_settings.frontend_origin_pattern,
		allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
		allow_headers=["content-type"],
	)
	app.add_middleware(OriginGuard, allowed_origin_pattern=app_settings.frontend_origin_pattern)

	app.include_router(projects.router)
	app.include_router(nodes.router)
	app.include_router(exports.router)
	app.include_router(generations.router)
	app.include_router(models.router)
	app.include_router(assets.router)
	app.include_router(library.router)
	app.include_router(priors.router)
	app.include_router(taste_priors.router)
	app.include_router(interfaces.router)
	return app


app = create_app()
