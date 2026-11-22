"""Alembic environment: run migrations against the configured database."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from smooth_diagrams.database.engine import create_engine
from smooth_diagrams.database.models import Base
from smooth_diagrams.settings import get_settings

config = context.config

# Use the server's database unless the caller already chose one.
if not config.get_main_option("sqlalchemy.url"):
	config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

if config.config_file_name is not None:
	fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
	"""Write the migration SQL to the output without connecting to a database."""
	context.configure(
		url=config.get_main_option("sqlalchemy.url"),
		target_metadata=target_metadata,
		literal_binds=True,
		dialect_opts={"paramstyle": "named"},
		render_as_batch=True,
	)

	with context.begin_transaction():
		context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
	"""Run the migrations on an open connection."""
	# Batch mode rebuilds a table to alter it, which is the only way SQLite can.
	context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)

	with context.begin_transaction():
		context.run_migrations()


async def run_async_migrations() -> None:
	"""Connect with the async driver and run the migrations."""
	connectable = create_engine(config.get_main_option("sqlalchemy.url"))

	async with connectable.connect() as connection:
		await connection.run_sync(do_run_migrations)

	await connectable.dispose()


if context.is_offline_mode():
	run_migrations_offline()
else:
	asyncio.run(run_async_migrations())
