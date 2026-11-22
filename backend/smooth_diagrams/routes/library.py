"""Routes for the library: reference images and nodes shared across projects."""

import uuid
from pathlib import PurePath
from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from smooth_diagrams.database import reference_queries
from smooth_diagrams.database.models import Asset, LibraryItem, LibraryItemKind, Node
from smooth_diagrams.routes.dependencies import (
	EmbedderDependency,
	FileStoreDependency,
	SessionDependency,
	SettingsDependency,
)
from smooth_diagrams.schemas import LibraryItemDetail, LibraryNodeInput
from smooth_diagrams.similarity import library_similarity
from smooth_diagrams.similarity.embedder import EmbedderUnavailableError
from smooth_diagrams.storage.uploads import store_image

router = APIRouter()

# Longest name given to a node item, which is taken from the node's prompt.
node_name_length = 60


@router.get("/library")
async def list_library(
	session: SessionDependency,
	file_store: FileStoreDependency,
	embedder: EmbedderDependency,
	sort: Literal["date", "name", "similarity"] = "date",
	similar_to: uuid.UUID | None = None,
) -> list[LibraryItemDetail]:
	"""Return every library item: newest first, by name, or by likeness to one of them."""
	if sort != "similarity":
		return await reference_queries.list_library_items(session, sort_by_name=sort == "name")

	if similar_to is None:
		raise HTTPException(
			status.HTTP_422_UNPROCESSABLE_CONTENT,
			"Sorting by similarity needs the item to compare the others with.",
		)
	try:
		return await library_similarity.sort_by_similarity(
			session, file_store, embedder, similar_to
		)
	except library_similarity.ItemNotFoundError as error:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Library item not found") from error
	except library_similarity.NoImageError as error:
		raise HTTPException(
			status.HTTP_409_CONFLICT, "That item has no image to compare the others with."
		) from error
	except EmbedderUnavailableError as error:
		raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error


@router.post("/library/images", status_code=status.HTTP_201_CREATED)
async def add_image(
	file: UploadFile,
	session: SessionDependency,
	file_store: FileStoreDependency,
	settings: SettingsDependency,
	name: Annotated[str | None, Form(max_length=200)] = None,
) -> LibraryItemDetail:
	"""Add an uploaded image to the library, named after its file unless a name is given."""
	asset = await store_image(file, file_store, session, settings.image_byte_limit)
	item = LibraryItem(
		kind=LibraryItemKind.IMAGE,
		name=(name or "").strip() or PurePath(asset.file_name).stem,
		asset_id=asset.id,
	)
	session.add(item)
	await session.commit()
	return reference_queries.build_library_item_detail(item, None, None)


@router.post("/library/nodes", status_code=status.HTTP_201_CREATED)
async def add_node(node_input: LibraryNodeInput, session: SessionDependency) -> LibraryItemDetail:
	"""Send a node to the library, or return its item when it is already there."""
	node = await session.get(Node, node_input.node_id)
	if node is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")

	# Keep one item per node, so sending a node twice changes nothing.
	existing = await session.execute(select(LibraryItem).where(LibraryItem.node_id == node.id))
	item = existing.scalar_one_or_none()
	if item is None:
		name = node.prompt.strip() or "Uploaded diagram"
		item = LibraryItem(kind=LibraryItemKind.NODE, name=name[:node_name_length], node_id=node.id)
		session.add(item)
		await session.commit()

	detail = await reference_queries.get_library_item_detail(session, item.id)
	assert detail is not None
	return detail


@router.delete("/library/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(
	item_id: uuid.UUID, session: SessionDependency, file_store: FileStoreDependency
) -> None:
	"""Remove an item from the library, along with its image file and the priors that use it."""
	item = await session.get(LibraryItem, item_id)
	if item is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Library item not found")

	asset = await session.get(Asset, item.asset_id) if item.asset_id else None
	await session.delete(item)
	if asset is not None:
		await session.delete(asset)
	await session.commit()

	# Remove the file last, so a failed commit never leaves a row without its file.
	if asset is not None:
		await file_store.delete(asset.storage_key)
