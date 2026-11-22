"""Server settings, read from the environment and from backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

backend_directory = Path(__file__).resolve().parent.parent
default_database_path = backend_directory / "data" / "smooth_diagrams.db"


class Settings(BaseSettings):
	"""Values that differ between machines or must stay out of the repo."""

	model_config = SettingsConfigDict(
		env_file=backend_directory / ".env",
		env_prefix="SMOOTH_DIAGRAMS_",
		extra="ignore",
	)

	# SQLAlchemy URL; swap it for a Postgres URL to move to Supabase.
	database_url: str = f"sqlite+aiosqlite:///{default_database_path.as_posix()}"

	# Pattern of the origins allowed to call the server. The default is this computer on any
	# port, because the frontend's dev server moves to another port when its usual one is taken.
	frontend_origin_pattern: str = r"http://(localhost|127\.0\.0\.1|\[::1\]):\d+"

	# Id of the model used when a generation does not name one; see model_catalog.py.
	default_model: str = "claude-opus-5-5"

	# Seconds the server waits for the viewer to report whether a step rendered.
	step_outcome_timeout: float = 30.0

	# Failed attempts in a row after which a generation stops.
	failure_limit: int = 3


@lru_cache
def get_settings() -> Settings:
	"""Return the settings, read once per process."""
	return Settings()
