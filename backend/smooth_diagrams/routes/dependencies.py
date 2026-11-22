"""Values the routes receive from the running app."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
	"""Yield a database session for one request."""
	async with request.app.state.session_factory() as session:
		yield session


SessionDependency = Annotated[AsyncSession, Depends(get_session)]
