"""Routes for a project's interface and its versions."""

import uuid

from fastapi import APIRouter, HTTPException, status

from smooth_diagrams.database import interface_queries
from smooth_diagrams.database.models import InterfaceVersion, Project
from smooth_diagrams.interface_settings import InterfaceSettings
from smooth_diagrams.routes.dependencies import SessionDependency, SettingsDependency
from smooth_diagrams.schemas import InterfaceSource, InterfaceState, RestoreInput

router = APIRouter()


async def find_project(session: SessionDependency, project_id: uuid.UUID) -> Project:
	"""Return a project, or answer that it does not exist."""
	project = await session.get(Project, project_id)
	if project is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
	return project


@router.get("/interface_versions")
async def list_interface_sources(session: SessionDependency) -> list[InterfaceSource]:
	"""Return every interface version a new project could start from."""
	return await interface_queries.list_interface_sources(session)


@router.get("/projects/{project_id}/interface")
async def get_interface(
	project_id: uuid.UUID, session: SessionDependency, settings: SettingsDependency
) -> InterfaceState:
	"""Return a project's current interface settings and its versions."""
	project = await find_project(session, project_id)
	return await interface_queries.build_interface_state(session, project, settings.default_model)


@router.put("/projects/{project_id}/interface")
async def save_interface(
	project_id: uuid.UUID,
	interface_settings: InterfaceSettings,
	session: SessionDependency,
	settings: SettingsDependency,
) -> InterfaceState:
	"""Store new interface settings, in a new version when the current one produced work."""
	project = await find_project(session, project_id)
	await interface_queries.save_settings(
		session, project, interface_settings, settings.default_model
	)
	return await interface_queries.build_interface_state(session, project, settings.default_model)


@router.post("/projects/{project_id}/interface/restore")
async def restore_interface(
	project_id: uuid.UUID,
	restore_input: RestoreInput,
	session: SessionDependency,
	settings: SettingsDependency,
) -> InterfaceState:
	"""Make an earlier version of a project's interface the current one again."""
	project = await find_project(session, project_id)
	version = await session.get(InterfaceVersion, restore_input.interface_version_id)
	if version is None or version.project_id != project.id:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Interface version not found")

	project.current_interface_version_id = version.id
	await session.commit()
	return await interface_queries.build_interface_state(session, project, settings.default_model)
