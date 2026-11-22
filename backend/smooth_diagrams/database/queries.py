"""Reads and writes shared by the HTTP routes and the generation session."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from smooth_diagrams.database.models import Node, NodeStatus, Piece, Project, Step
from smooth_diagrams.schemas import NodeSummary, ProjectSummary

# ---------------------------------------------------------------------------
# Projects and pieces
# ---------------------------------------------------------------------------


async def list_project_summaries(session: AsyncSession) -> list[ProjectSummary]:
	"""Return every project, newest first, with its piece count and cover."""
	piece_count = (
		select(func.count())
		.where(Piece.project_id == Project.id)
		.correlate(Project)
		.scalar_subquery()
	)
	cover_svg = (
		select(Step.render_svg)
		.join(Node, Step.node_id == Node.id)
		.join(Piece, Node.piece_id == Piece.id)
		.where(Piece.project_id == Project.id, Step.is_rejected.is_(False))
		.order_by(Step.created_at.desc())
		.limit(1)
		.correlate(Project)
		.scalar_subquery()
	)

	rows = await session.execute(
		select(Project, piece_count, cover_svg).order_by(Project.created_at.desc())
	)
	return [
		ProjectSummary(
			id=project.id,
			name=project.name,
			created_at=project.created_at,
			piece_count=count,
			cover_svg=cover,
		)
		for project, count, cover in rows
	]


async def get_project(session: AsyncSession, project_id: uuid.UUID) -> Project | None:
	"""Return one project with its pieces loaded."""
	result = await session.execute(
		select(Project).where(Project.id == project_id).options(selectinload(Project.pieces))
	)
	return result.scalar_one_or_none()


async def create_project(session: AsyncSession, name: str) -> Project:
	"""Create a project with a first piece, so it can be worked in straight away."""
	project = Project(name=name, pieces=[Piece(name="Piece 1")])
	session.add(project)
	await session.commit()
	return project


async def create_piece(session: AsyncSession, project: Project, name: str) -> Piece:
	"""Add a piece to a project."""
	piece = Piece(project_id=project.id, name=name)
	session.add(piece)
	await session.commit()
	return piece


# ---------------------------------------------------------------------------
# Nodes and steps
# ---------------------------------------------------------------------------


async def list_node_summaries(session: AsyncSession, piece_id: uuid.UUID) -> list[NodeSummary]:
	"""Return a piece's nodes, oldest first, each with its step count and newest render."""
	is_accepted = (Step.node_id == Node.id) & Step.is_rejected.is_(False)
	step_count = select(func.count()).where(is_accepted).correlate(Node).scalar_subquery()
	render_svg = (
		select(Step.render_svg)
		.where(is_accepted)
		.order_by(Step.step_index.desc())
		.limit(1)
		.correlate(Node)
		.scalar_subquery()
	)

	rows = await session.execute(
		select(Node, step_count, render_svg)
		.where(Node.piece_id == piece_id)
		.order_by(Node.created_at)
	)
	return [build_node_summary(node, count, render) for node, count, render in rows]


def build_node_summary(node: Node, step_count: int, render_svg: str | None) -> NodeSummary:
	"""Return the summary of a node from its row and its two computed values."""
	return NodeSummary(
		id=node.id,
		piece_id=node.piece_id,
		parent_node_id=node.parent_node_id,
		parent_step_id=node.parent_step_id,
		kind=node.kind,
		status=node.status,
		prompt=node.prompt,
		model=node.model,
		is_step_by_step=node.is_step_by_step,
		failure_message=node.failure_message,
		created_at=node.created_at,
		step_count=step_count,
		render_svg=render_svg,
	)


async def get_node(session: AsyncSession, node_id: uuid.UUID) -> Node | None:
	"""Return one node with its steps and the step it starts from."""
	result = await session.execute(
		select(Node)
		.where(Node.id == node_id)
		.options(selectinload(Node.steps), selectinload(Node.parent_step))
	)
	return result.scalar_one_or_none()


async def get_step(session: AsyncSession, step_id: uuid.UUID) -> Step | None:
	"""Return one step."""
	return await session.get(Step, step_id)


async def mark_interrupted_nodes(session: AsyncSession) -> None:
	"""Mark nodes left generating by a server that went away as stopped."""
	result = await session.execute(select(Node).where(Node.status == NodeStatus.GENERATING))
	for node in result.scalars():
		node.status = NodeStatus.STOPPED
	await session.commit()
