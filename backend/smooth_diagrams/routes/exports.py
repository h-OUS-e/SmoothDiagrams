"""Route that remembers the exports of a node."""

import uuid

from fastapi import APIRouter, HTTPException, status

from smooth_diagrams.database.models import Export, Node, Step
from smooth_diagrams.routes.dependencies import SessionDependency
from smooth_diagrams.schemas import ExportDetail, ExportInput

router = APIRouter()


@router.post("/nodes/{node_id}/exports", status_code=status.HTTP_201_CREATED)
async def add_export(
	node_id: uuid.UUID, export_input: ExportInput, session: SessionDependency
) -> ExportDetail:
	"""Remember that the director exported a step of a node.

	The file itself is made in the browser and is not stored; the settings kept here are
	enough to make it again.
	"""
	if await session.get(Node, node_id) is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")

	# Accept only a step of this node, so an export never points into another node.
	step = await session.get(Step, export_input.step_id)
	if step is None or step.node_id != node_id:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Step not found in this node")

	export = Export(
		node_id=node_id,
		step_id=step.id,
		format=export_input.format,
		parameter_values=export_input.parameter_values,
		animation_time=export_input.animation_time,
		pixel_width=export_input.pixel_width,
		pixel_height=export_input.pixel_height,
	)
	session.add(export)
	await session.commit()
	return ExportDetail.model_validate(export)
