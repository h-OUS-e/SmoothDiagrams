"""Routes for nodes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile, status

from smooth_diagrams.database import queries
from smooth_diagrams.database.models import Node, NodeKind, NodeStatus, Piece, Step
from smooth_diagrams.generation.taste_reasons import NoParentError, offer_taste_reasons
from smooth_diagrams.providers.base import ModelCallError
from smooth_diagrams.routes.dependencies import (
	FileStoreDependency,
	SessionDependency,
	SettingsDependency,
)
from smooth_diagrams.schemas import (
	NodeDetail,
	ParameterValuesInput,
	TasteReasonCandidates,
	TasteReasonInput,
)
from smooth_diagrams.storage.uploads import store_image

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


# ---------------------------------------------------------------------------
# Uploaded nodes
# ---------------------------------------------------------------------------


@router.post("/pieces/{piece_id}/uploaded_nodes", status_code=status.HTTP_201_CREATED)
async def add_uploaded_node(
	piece_id: uuid.UUID,
	file: UploadFile,
	session: SessionDependency,
	file_store: FileStoreDependency,
	settings: SettingsDependency,
	parent_step_id: Annotated[uuid.UUID | None, Form()] = None,
) -> NodeDetail:
	"""Add an image the director edited outside the app as a new node of a piece.

	The node hangs under the step it is an edit of, when one is named, and stays a root otherwise.
	"""
	if await session.get(Piece, piece_id) is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Piece not found")

	# Find the step the image is an edit of, which must belong to the same piece.
	parent_step: Step | None = None
	parent_node: Node | None = None
	if parent_step_id is not None:
		parent_step = await session.get(Step, parent_step_id)
		parent_node = await session.get(Node, parent_step.node_id) if parent_step else None
		if parent_step is None or parent_node is None or parent_node.piece_id != piece_id:
			raise HTTPException(status.HTTP_404_NOT_FOUND, "Step not found in this piece")

	asset = await store_image(file, file_store, session, settings.image_byte_limit)
	node = Node(
		piece_id=piece_id,
		parent_node_id=parent_node.id if parent_node else None,
		parent_step_id=parent_step.id if parent_step else None,
		kind=NodeKind.UPLOADED,
		status=NodeStatus.FINISHED,
		prompt="",
		is_step_by_step=False,
		parameter_values={},
		image_asset_id=asset.id,
	)
	session.add(node)
	await session.commit()

	stored_node = await queries.get_node(session, node.id)
	return NodeDetail.model_validate(stored_node)


# ---------------------------------------------------------------------------
# Taste reasons
# ---------------------------------------------------------------------------


@router.post("/nodes/{node_id}/taste_reason_candidates")
async def offer_taste_reason_candidates(
	node_id: uuid.UUID, request: Request, session: SessionDependency, settings: SettingsDependency
) -> TasteReasonCandidates:
	"""Ask the taste reason agent why the director may have continued from this node's parent."""
	node = await session.get(Node, node_id)
	if node is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")

	try:
		candidates = await offer_taste_reasons(
			session, request.app.state.provider, settings.taste_reason_model, node
		)
	except NoParentError as error:
		raise HTTPException(
			status.HTTP_409_CONFLICT, "This node continues no other node."
		) from error
	except ModelCallError as error:
		raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
	return TasteReasonCandidates(candidates=candidates)


@router.patch("/nodes/{node_id}/taste_reason")
async def set_taste_reason(
	node_id: uuid.UUID, reason_input: TasteReasonInput, session: SessionDependency
) -> NodeDetail:
	"""Store the reason the director picked or wrote; an empty one clears it."""
	node = await queries.get_node(session, node_id)
	if node is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")

	node.taste_reason = (reason_input.taste_reason or "").strip() or None
	await session.commit()
	return NodeDetail.model_validate(node)
