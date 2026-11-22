"""Sort the library by how much each item looks like one of its items."""

import asyncio
import logging
import uuid
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smooth_diagrams.database import reference_queries
from smooth_diagrams.database.models import Asset, LibraryItem, Node, Step
from smooth_diagrams.schemas import LibraryItemDetail
from smooth_diagrams.similarity.embedder import ImageEmbedder, ImageUnreadableError
from smooth_diagrams.similarity.rasterize import rasterize_svg
from smooth_diagrams.storage.file_store import FileStore

logger = logging.getLogger(__name__)


class ItemNotFoundError(Exception):
	"""The item to compare the library with is not in the library."""


class NoImageError(Exception):
	"""The item to compare the library with has nothing to look at."""


@dataclass
class ItemImage:
	"""A library item and where the image it is judged by comes from."""

	item: LibraryItem

	# The asset or step that holds the image; None when the item has nothing to look at.
	source_id: uuid.UUID | None
	is_asset: bool


async def list_item_images(session: AsyncSession) -> list[ItemImage]:
	"""Return every library item with the asset or the step its image comes from."""
	newest_step_id = (
		select(Step.id)
		.where(Step.node_id == LibraryItem.node_id, Step.is_rejected.is_(False))
		.order_by(Step.step_index.desc())
		.limit(1)
		.correlate(LibraryItem)
		.scalar_subquery()
	)
	rows = await session.execute(
		select(LibraryItem, Node.image_asset_id, newest_step_id).outerjoin(
			Node, LibraryItem.node_id == Node.id
		)
	)

	# An image item and an uploaded node show an asset; any other node shows its newest step.
	item_images: list[ItemImage] = []
	for item, node_image_asset_id, step_id in rows:
		asset_id = item.asset_id or node_image_asset_id
		item_images.append(
			ItemImage(item=item, source_id=asset_id or step_id, is_asset=asset_id is not None)
		)
	return item_images


async def read_image(
	session: AsyncSession, file_store: FileStore, item_image: ItemImage
) -> bytes | None:
	"""Return the bytes of the image an item is judged by, or None when they cannot be had."""
	try:
		if item_image.is_asset:
			asset = await session.get(Asset, item_image.source_id)
			return await file_store.read(asset.storage_key) if asset else None

		step = await session.get(Step, item_image.source_id)
		return await asyncio.to_thread(rasterize_svg, step.render_svg) if step else None
	except (OSError, ValueError) as error:
		logger.warning("Library item %s has no usable image: %s", item_image.item.id, error)
		return None


def has_current_embedding(item_image: ItemImage, embedder: ImageEmbedder) -> bool:
	"""Return whether an item's stored embedding was made by this model from its current image."""
	item = item_image.item
	return (
		item.embedding is not None
		and item.embedding_model == embedder.model_name
		and item.embedding_source_id == item_image.source_id
	)


async def refresh_embeddings(
	session: AsyncSession,
	file_store: FileStore,
	embedder: ImageEmbedder,
	item_images: list[ItemImage],
) -> None:
	"""Compute and store the embedding of every item that lacks a current one.

	Raises:
		EmbedderUnavailableError: The embedding model could not be loaded.
	"""
	# Collect the images of the items whose embedding is missing or out of date.
	waiting: list[tuple[ItemImage, bytes]] = []
	for item_image in item_images:
		if item_image.source_id is None or has_current_embedding(item_image, embedder):
			continue
		image = await read_image(session, file_store, item_image)
		if image is not None:
			waiting.append((item_image, image))
	if not waiting:
		return

	# Embed one image at a time when the batch fails, so one unreadable file spoils only itself.
	images = [image for _, image in waiting]
	try:
		embeddings: list[np.ndarray | None] = list(await asyncio.to_thread(embedder.embed, images))
	except ImageUnreadableError:
		embeddings = []
		for image in images:
			try:
				embeddings.append((await asyncio.to_thread(embedder.embed, [image]))[0])
			except ImageUnreadableError:
				embeddings.append(None)

	for (item_image, _), embedding in zip(waiting, embeddings, strict=True):
		if embedding is None:
			logger.warning("Library item %s has an image that cannot be read", item_image.item.id)
			continue
		item_image.item.embedding = embedding.astype(np.float32).tobytes()
		item_image.item.embedding_model = embedder.model_name
		item_image.item.embedding_source_id = item_image.source_id
	await session.commit()


async def sort_by_similarity(
	session: AsyncSession,
	file_store: FileStore,
	embedder: ImageEmbedder,
	compared_item_id: uuid.UUID,
) -> list[LibraryItemDetail]:
	"""Return every library item, ordered by how much it looks like one of them.

	Embeddings are computed on first need and kept on the items, so only new items cost
	anything on later calls.

	Args:
		session: Database session.
		file_store: Where uploaded images are kept.
		embedder: The model that turns images into embeddings.
		compared_item_id: The item the others are compared with.

	Returns:
		The compared item first, then the others from most to least alike. Items that have
		nothing to look at come last, newest first.

	Raises:
		ItemNotFoundError: The compared item is not in the library.
		NoImageError: The compared item has nothing to look at.
		EmbedderUnavailableError: The embedding model could not be loaded.
	"""
	item_images = await list_item_images(session)
	compared = next((entry for entry in item_images if entry.item.id == compared_item_id), None)
	if compared is None:
		raise ItemNotFoundError
	await refresh_embeddings(session, file_store, embedder, item_images)
	if not has_current_embedding(compared, embedder):
		raise NoImageError

	# Score each item by its cosine similarity, which is a dot product of vectors of length one.
	compared_embedding = np.frombuffer(compared.item.embedding, dtype=np.float32)
	scores: dict[uuid.UUID, float] = {}
	for item_image in item_images:
		if has_current_embedding(item_image, embedder):
			embedding = np.frombuffer(item_image.item.embedding, dtype=np.float32)
			scores[item_image.item.id] = float(embedding @ compared_embedding)

	# Keep the newest-first order among items that cannot be scored, which a stable sort does.
	details = await reference_queries.list_library_items(session, sort_by_name=False)
	lowest_score = -2.0
	return sorted(
		details,
		key=lambda detail: (
			detail.id != compared_item_id,
			-scores.get(detail.id, lowest_score),
		),
	)
