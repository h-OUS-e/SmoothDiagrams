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

	# Folder that holds uploaded images.
	assets_directory: Path = backend_directory / "data" / "assets"

	# Largest image accepted, in bytes; models refuse images much larger than this.
	image_byte_limit: int = 5_000_000

	# Id of the model that offers taste reasons, which needs speed more than depth.
	taste_reason_model: str = "claude-sonnet-5-5"

	# The image model that sorts the library by similarity: its Hugging Face repository, the
	# file in it, and the exact revision, so a changed upload is never picked up unnoticed.
	similarity_model_repository: str = "Xenova/clip-vit-base-patch32"
	similarity_model_file: str = "onnx/vision_model_quantized.onnx"
	similarity_model_revision: str = "6b7c523703ae26e39be4b03774966f8571c7f523"


@lru_cache
def get_settings() -> Settings:
	"""Return the settings, read once per process."""
	return Settings()
