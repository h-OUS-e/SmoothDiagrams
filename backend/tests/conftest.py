"""Shared test setup: an app on a throwaway database with a scripted model."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smooth_diagrams.main import create_app
from smooth_diagrams.settings import Settings
from tests.color_embedder import ColorEmbedder
from tests.scripted_provider import ScriptedProvider


@pytest.fixture
def scripted_provider() -> ScriptedProvider:
	"""Return the provider the test app talks to; tests append turns to it."""
	return ScriptedProvider(turns=[])


@pytest.fixture
def color_embedder() -> ColorEmbedder:
	"""Return the embedder the test app sorts its library with."""
	return ColorEmbedder()


@pytest.fixture
def client(
	tmp_path: Path, scripted_provider: ScriptedProvider, color_embedder: ColorEmbedder
) -> Iterator[TestClient]:
	"""Return a client for an app that uses a fresh database file."""
	settings = Settings(
		database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
		assets_directory=tmp_path / "assets",
		step_outcome_timeout=2.0,
		failure_limit=3,
	)
	app = create_app(settings=settings, provider=scripted_provider, embedder=color_embedder)
	with TestClient(app) as test_client:
		yield test_client
