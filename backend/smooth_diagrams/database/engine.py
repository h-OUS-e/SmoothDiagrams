"""Database engine, sessions, and migrations."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
	AsyncEngine,
	AsyncSession,
	async_sessionmaker,
	create_async_engine,
)

from smooth_diagrams.settings import backend_directory

SessionFactory = async_sessionmaker[AsyncSession]


def create_engine(database_url: str) -> AsyncEngine:
	"""Return an engine for the database, creating the folder of a SQLite file if needed."""
	url = make_url(database_url)
	is_sqlite = url.get_backend_name() == "sqlite"

	# Make sure the SQLite file has a folder to live in.
	if is_sqlite and url.database and url.database != ":memory:":
		Path(url.database).parent.mkdir(parents=True, exist_ok=True)

	engine = create_async_engine(database_url)

	# Turn on foreign keys, which SQLite leaves off for every new connection.
	if is_sqlite:

		@event.listens_for(engine.sync_engine, "connect")
		def enable_foreign_keys(dbapi_connection, connection_record) -> None:
			cursor = dbapi_connection.cursor()
			cursor.execute("PRAGMA foreign_keys=ON")
			cursor.close()

	return engine


def create_session_factory(engine: AsyncEngine) -> SessionFactory:
	"""Return a factory for sessions that keep loaded objects usable after commit."""
	return async_sessionmaker(engine, expire_on_commit=False)


def build_alembic_config(database_url: str) -> Config:
	"""Return the Alembic configuration pointed at one database."""
	config = Config(str(backend_directory / "alembic.ini"))
	config.set_main_option("script_location", str(backend_directory / "migrations"))
	config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
	return config


def run_migrations(database_url: str) -> None:
	"""Bring the database schema up to the newest migration. Blocking; run it off the event loop."""
	command.upgrade(build_alembic_config(database_url), "head")
