"""Reads and writes for interface versions."""

import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from smooth_diagrams.database.models import InterfaceVersion, Node, Project
from smooth_diagrams.interface_settings import InterfaceSettings, build_default_settings
from smooth_diagrams.schemas import InterfaceSource, InterfaceState, InterfaceVersionSummary


async def get_current_version(
	session: AsyncSession, project: Project, default_model: str
) -> InterfaceVersion:
	"""Return a project's current interface version, creating its first one when it has none."""
	if project.current_interface_version_id is not None:
		version = await session.get(InterfaceVersion, project.current_interface_version_id)
		if version is not None:
			return version

	settings = build_default_settings(default_model)
	return await add_version(session, project, settings, source_version=None)


async def add_version(
	session: AsyncSession,
	project: Project,
	settings: InterfaceSettings,
	source_version: InterfaceVersion | None,
) -> InterfaceVersion:
	"""Add a version after a project's newest one and make it the current version."""
	newest_number = await session.scalar(
		select(func.max(InterfaceVersion.version_number)).where(
			InterfaceVersion.project_id == project.id
		)
	)
	version = InterfaceVersion(
		id=uuid.uuid4(),
		project_id=project.id,
		version_number=(newest_number or 0) + 1,
		settings=settings.model_dump(mode="json"),
		source_version_id=source_version.id if source_version else None,
	)
	session.add(version)
	await session.flush()

	project.current_interface_version_id = version.id
	await session.commit()
	return version


async def is_frozen(session: AsyncSession, version: InterfaceVersion) -> bool:
	"""Return whether a version produced work, and so must never change again.

	A version is frozen once a node was made with it or another version was copied from it.
	"""
	made_a_node = exists().where(Node.interface_version_id == version.id)
	was_copied = exists().where(InterfaceVersion.source_version_id == version.id)
	return bool(await session.scalar(select(made_a_node | was_copied)))


async def save_settings(
	session: AsyncSession, project: Project, settings: InterfaceSettings, default_model: str
) -> InterfaceVersion:
	"""Store new settings for a project and return the version that now holds them.

	Args:
		session: Database session to write with.
		project: The project whose interface changes.
		settings: The complete new settings.
		default_model: Model for the first version, when the project has none yet.

	Returns:
		The current version: the same one when it was still unused or nothing changed,
		a new one when the old version was frozen.
	"""
	current = await get_current_version(session, project, default_model)
	stored_settings = settings.model_dump(mode="json")
	if current.settings == stored_settings:
		return current

	# Keep a version that produced work as it is, and continue in a new one.
	if await is_frozen(session, current):
		return await add_version(session, project, settings, source_version=current)

	current.settings = stored_settings
	await session.commit()
	return current


async def build_interface_state(
	session: AsyncSession, project: Project, default_model: str
) -> InterfaceState:
	"""Return a project's current settings and a summary of every version it has."""
	current = await get_current_version(session, project, default_model)

	node_count = (
		select(func.count())
		.where(Node.interface_version_id == InterfaceVersion.id)
		.correlate(InterfaceVersion)
		.scalar_subquery()
	)
	rows = await session.execute(
		select(InterfaceVersion, node_count)
		.where(InterfaceVersion.project_id == project.id)
		.order_by(InterfaceVersion.version_number.desc())
	)
	versions = [
		InterfaceVersionSummary(
			id=version.id,
			version_number=version.version_number,
			created_at=version.created_at,
			node_count=count,
			is_current=version.id == current.id,
		)
		for version, count in rows
	]

	return InterfaceState(
		current_version_id=current.id,
		version_number=current.version_number,
		settings=InterfaceSettings.model_validate(current.settings),
		versions=versions,
	)


async def list_interface_sources(session: AsyncSession) -> list[InterfaceSource]:
	"""Return every interface version of every project, newest first, to start a project from."""
	rows = await session.execute(
		select(InterfaceVersion, Project.name)
		.join(Project, InterfaceVersion.project_id == Project.id)
		.order_by(Project.created_at.desc(), InterfaceVersion.version_number.desc())
	)
	return [
		InterfaceSource(
			id=version.id,
			project_id=version.project_id,
			project_name=project_name,
			version_number=version.version_number,
			created_at=version.created_at,
		)
		for version, project_name in rows
	]
