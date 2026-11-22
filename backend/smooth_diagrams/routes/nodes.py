"""Routes for nodes."""

import uuid

from fastapi import APIRouter, HTTPException, status

from smooth_diagrams.database import queries
from smooth_diagrams.routes.dependencies import SessionDependency
from smooth_diagrams.schemas import NodeDetail, ParameterValuesInput

router = APIRouter()


@router.get("/nodes/{node_id}")
async def get_node(node_id: uuid.UUID, session: SessionDependency) -> NodeDetail:
	"""Return one node with its steps and the step it starts from."""
	node = await queries.get_node(session, node_id)
	if node is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")
	return NodeDetail.model_validate(node)


@router.patch("/nodes/{node_id}/parameter_values")
async def set_parameter_values(
	node_id: uuid.UUID, values_input: ParameterValuesInput, session: SessionDependency
) -> NodeDetail:
	"""Store the values the director chose for a node's exposed parameters."""
	node = await queries.get_node(session, node_id)
	if node is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")

	node.parameter_values = values_input.parameter_values
	await session.commit()
	return NodeDetail.model_validate(node)
