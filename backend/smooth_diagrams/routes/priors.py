"""Routes for a project's priors."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from smooth_diagrams.database import reference_queries
from smooth_diagrams.database.models import LibraryItem, Prior, Project
from smooth_diagrams.routes.dependencies import SessionDependency
from smooth_diagrams.schemas import PriorChanges, PriorDetail, PriorInput

router = APIRouter()


@router.get("/projects/{project_id}/priors")
async def list_priors(project_id: uuid.UUID, session: SessionDependency) -> list[PriorDetail]:
	"""Return a project's priors, oldest first."""
	return await reference_queries.list_prior_details(session, project_id)


@router.post("/projects/{project_id}/priors", status_code=status.HTTP_201_CREATED)
async def add_prior(
	project_id: uuid.UUID, prior_input: PriorInput, session: SessionDependency
) -> PriorDetail:
	"""Add a prior to a project: a library item, or a text with a name."""
	if await session.get(Project, project_id) is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

	# Add a text prior, which carries its own name and words.
	if prior_input.library_item_id is None:
		if prior_input.name is None or prior_input.text_content is None:
			raise HTTPException(
				status.HTTP_422_UNPROCESSABLE_CONTENT,
				"A prior needs a library item, or a name and text.",
			)
		prior = Prior(
			project_id=project_id,
			name=prior_input.name.strip(),
			text_content=prior_input.text_content,
		)
		session.add(prior)
		await session.commit()
		return await reference_queries.build_prior_detail(session, prior)

	# Add a library item, or return the prior that already uses it.
	if await session.get(LibraryItem, prior_input.library_item_id) is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Library item not found")
	existing = await session.execute(
		select(Prior).where(
			Prior.project_id == project_id,
			Prior.library_item_id == prior_input.library_item_id,
		)
	)
	prior = existing.scalar_one_or_none()
	if prior is None:
		prior = Prior(project_id=project_id, library_item_id=prior_input.library_item_id)
		session.add(prior)
		await session.commit()
	return await reference_queries.build_prior_detail(session, prior)


@router.patch("/priors/{prior_id}")
async def change_prior(
	prior_id: uuid.UUID, changes: PriorChanges, session: SessionDependency
) -> PriorDetail:
	"""Change a prior's note, its on or off state, or the name and text of a text prior."""
	prior = await session.get(Prior, prior_id)
	if prior is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Prior not found")

	# Apply only the fields that were sent.
	for field_name, value in changes.model_dump(exclude_unset=True).items():
		if value is not None:
			setattr(prior, field_name, value)
	await session.commit()
	return await reference_queries.build_prior_detail(session, prior)


@router.delete("/priors/{prior_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_prior(prior_id: uuid.UUID, session: SessionDependency) -> None:
	"""Remove a prior from its project; a library item it points at stays in the library."""
	prior = await session.get(Prior, prior_id)
	if prior is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Prior not found")

	await session.delete(prior)
	await session.commit()
