"""Values the routes receive from the running app."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from smooth_diagrams.settings import Settings
from smooth_diagrams.similarity.embedder import ImageEmbedder
from smooth_diagrams.storage.file_store import FileStore


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
	"""Yield a database session for one request."""
	async with request.app.state.session_factory() as session:
		yield session


def get_file_store(request: Request) -> FileStore:
	"""Return the store that holds uploaded files."""
	return request.app.state.file_store


def get_settings(request: Request) -> Settings:
	"""Return the settings the app was started with."""
	return request.app.state.settings


def get_embedder(request: Request) -> ImageEmbedder:
	"""Return the model that turns images into embeddings."""
	return request.app.state.embedder


SessionDependency = Annotated[AsyncSession, Depends(get_session)]
FileStoreDependency = Annotated[FileStore, Depends(get_file_store)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
EmbedderDependency = Annotated[ImageEmbedder, Depends(get_embedder)]
