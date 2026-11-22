"""Routes for projects and their pieces."""

import uuid

from fastapi import APIRouter, HTTPException, status

from smooth_diagrams.database import queries
from smooth_diagrams.database.models import Piece
from smooth_diagrams.routes.dependencies import SessionDependency
from smooth_diagrams.schemas import (
	NameInput,
	PieceDetail,
	PieceSummary,
	ProjectDetail,
	ProjectSummary,
)

router = APIRouter()


@router.get("/projects")
async def list_projects(session: SessionDependency) -> list[ProjectSummary]:
	"""Return every project, newest first."""
	return await queries.list_project_summaries(session)


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(name_input: NameInput, session: SessionDependency) -> ProjectDetail:
	"""Create a project with a first piece."""
	project = await queries.create_project(session, name_input.name.strip())
	return ProjectDetail.model_validate(await queries.get_project(session, project.id))


@router.get("/projects/{project_id}")
async def get_project(project_id: uuid.UUID, session: SessionDependency) -> ProjectDetail:
	"""Return one project with its pieces."""
	project = await queries.get_project(session, project_id)
	if project is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
	return ProjectDetail.model_validate(project)


@router.patch("/projects/{project_id}")
async def rename_project(
	project_id: uuid.UUID, name_input: NameInput, session: SessionDependency
) -> ProjectDetail:
	"""Rename a project."""
	project = await queries.get_project(session, project_id)
	if project is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

	project.name = name_input.name.strip()
	await session.commit()
	return ProjectDetail.model_validate(project)


@router.post("/projects/{project_id}/pieces", status_code=status.HTTP_201_CREATED)
async def create_piece(
	project_id: uuid.UUID, name_input: NameInput, session: SessionDependency
) -> PieceSummary:
	"""Add a piece to a project."""
	project = await queries.get_project(session, project_id)
	if project is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

	piece = await queries.create_piece(session, project, name_input.name.strip())
	return PieceSummary.model_validate(piece)


@router.get("/pieces/{piece_id}")
async def get_piece(piece_id: uuid.UUID, session: SessionDependency) -> PieceDetail:
	"""Return one piece with a summary of every node in its tree."""
	piece = await session.get(Piece, piece_id)
	if piece is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Piece not found")

	return PieceDetail(
		id=piece.id,
		project_id=piece.project_id,
		name=piece.name,
		created_at=piece.created_at,
		nodes=await queries.list_node_summaries(session, piece.id),
	)


@router.patch("/pieces/{piece_id}")
async def rename_piece(
	piece_id: uuid.UUID, name_input: NameInput, session: SessionDependency
) -> PieceSummary:
	"""Rename a piece."""
	piece = await session.get(Piece, piece_id)
	if piece is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Piece not found")

	piece.name = name_input.name.strip()
	await session.commit()
	return PieceSummary.model_validate(piece)
