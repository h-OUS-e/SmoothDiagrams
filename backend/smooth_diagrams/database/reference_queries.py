"""Reads for the library, priors, and taste priors."""

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from smooth_diagrams.database.models import LibraryItem, Node, Prior, Step
from smooth_diagrams.schemas import LibraryItemDetail, PriorDetail


def select_library_items() -> Select[tuple[LibraryItem, str | None, uuid.UUID | None]]:
	"""Return a query for library items with what their thumbnails need.

	Each row holds the item, the newest kept render of the node it points at, and the
	image of that node when it is an uploaded one.
	"""
	newest_render = (
		select(Step.render_svg)
		.where(Step.node_id == LibraryItem.node_id, Step.is_rejected.is_(False))
		.order_by(Step.step_index.desc())
		.limit(1)
		.correlate(LibraryItem)
		.scalar_subquery()
	)
	return select(LibraryItem, newest_render, Node.image_asset_id).outerjoin(
		Node, LibraryItem.node_id == Node.id
	)


def build_library_item_detail(
	item: LibraryItem, render_svg: str | None, node_image_asset_id: uuid.UUID | None
) -> LibraryItemDetail:
	"""Return the detail of a library item from one row of the library query."""
	return LibraryItemDetail(
		id=item.id,
		kind=item.kind,
		name=item.name,
		asset_id=item.asset_id or node_image_asset_id,
		node_id=item.node_id,
		created_at=item.created_at,
		render_svg=render_svg,
	)


async def list_library_items(session: AsyncSession, sort_by_name: bool) -> list[LibraryItemDetail]:
	"""Return every library item, by name or newest first."""
	order = LibraryItem.name if sort_by_name else LibraryItem.created_at.desc()
	rows = await session.execute(select_library_items().order_by(order))
	return [build_library_item_detail(*row) for row in rows]


async def get_library_item_detail(
	session: AsyncSession, item_id: uuid.UUID
) -> LibraryItemDetail | None:
	"""Return one library item with what its thumbnail needs."""
	rows = await session.execute(select_library_items().where(LibraryItem.id == item_id))
	row = rows.one_or_none()
	return build_library_item_detail(*row) if row else None


async def build_prior_detail(session: AsyncSession, prior: Prior) -> PriorDetail:
	"""Return the detail of a prior, named after its library item unless it has its own name."""
	item_detail = (
		await get_library_item_detail(session, prior.library_item_id)
		if prior.library_item_id
		else None
	)
	return PriorDetail(
		id=prior.id,
		project_id=prior.project_id,
		name=prior.name or (item_detail.name if item_detail else "Text"),
		text_content=prior.text_content,
		library_item=item_detail,
		prior_note=prior.prior_note,
		is_enabled=prior.is_enabled,
		created_at=prior.created_at,
	)


async def list_prior_details(session: AsyncSession, project_id: uuid.UUID) -> list[PriorDetail]:
	"""Return a project's priors, oldest first."""
	result = await session.execute(
		select(Prior)
		.where(Prior.project_id == project_id)
		.options(selectinload(Prior.library_item))
		.order_by(Prior.created_at)
	)
	return [await build_prior_detail(session, prior) for prior in result.scalars()]
