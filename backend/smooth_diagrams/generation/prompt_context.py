"""Gather what a generation knows beyond the request: taste priors, priors, taste reasons."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from smooth_diagrams.database.models import (
	Asset,
	LibraryItem,
	Node,
	Prior,
	Step,
	TastePrior,
	TastePriorKind,
)
from smooth_diagrams.providers.base import PromptImage
from smooth_diagrams.storage.file_store import FileStore


@dataclass(frozen=True)
class ContextSection:
	"""One reference shown to the model: a heading, text, and possibly an image."""

	heading: str
	body: str
	image: PromptImage | None = None


@dataclass(frozen=True)
class PromptContext:
	"""Everything a generation is told besides the director's request."""

	taste_sections: list[ContextSection] = field(default_factory=list)
	prior_sections: list[ContextSection] = field(default_factory=list)

	# Taste reasons picked on the branch, oldest first.
	taste_reasons: list[str] = field(default_factory=list)

	# The image of the uploaded node the generation continues from, if it continues one.
	edited_render: PromptImage | None = None


async def read_image(file_store: FileStore, asset: Asset) -> PromptImage:
	"""Return an asset's bytes in the form a model provider takes."""
	return PromptImage(media_type=asset.media_type, data=await file_store.read(asset.storage_key))


async def list_ancestors(session: AsyncSession, node_id: uuid.UUID | None) -> list[Node]:
	"""Return a node and the nodes it descends from, oldest first."""
	ancestors: list[Node] = []
	seen_ids: set[uuid.UUID] = set()

	# Walk up the parents, stopping at the root or at a loop that should never exist.
	while node_id is not None and node_id not in seen_ids:
		node = await session.get(Node, node_id)
		if node is None:
			break
		seen_ids.add(node_id)
		ancestors.append(node)
		node_id = node.parent_node_id

	ancestors.reverse()
	return ancestors


async def describe_node(session: AsyncSession, node: Node) -> str:
	"""Return how a node came to be and its final source, for use as a prior."""
	# Tell the story of the branch through the requests that shaped it.
	ancestors = await list_ancestors(session, node.id)
	requests = [ancestor.prompt for ancestor in ancestors if ancestor.prompt]
	lines = ["A diagram made earlier."]
	if requests:
		lines.append("It grew out of these requests, in order:")
		lines.extend(f"{position}. {request}" for position, request in enumerate(requests, 1))

	# Add the captions of the node's own steps and the source they ended at.
	result = await session.execute(
		select(Step)
		.where(Step.node_id == node.id, Step.is_rejected.is_(False))
		.order_by(Step.step_index)
	)
	steps = list(result.scalars())
	if steps:
		lines.append("Captions of its steps:")
		lines.extend(f"- {step.step_reasoning}" for step in steps)
		lines.append(f"Its source:\n```svelte\n{steps[-1].source}\n```")
	return "\n".join(lines)


async def build_prior_section(
	session: AsyncSession, file_store: FileStore, prior: Prior
) -> ContextSection | None:
	"""Return what one project prior shows the model, or None when it has nothing to show."""
	note = f"The director's note on it: {prior.prior_note}" if prior.prior_note.strip() else ""
	item = prior.library_item

	# A text prior carries its own words.
	if item is None:
		if not prior.text_content:
			return None
		body = "\n\n".join(part for part in (prior.text_content, note) if part)
		return ContextSection(heading=prior.name or "Text", body=body)

	# An image prior is attached; an uploaded node counts as an image.
	asset = item.asset or (item.node.image_asset if item.node else None)
	if asset is not None:
		return ContextSection(
			heading=item.name, body=note, image=await read_image(file_store, asset)
		)

	if item.node is None:
		return None
	description = await describe_node(session, item.node)
	return ContextSection(heading=item.name, body="\n\n".join(filter(None, (note, description))))


async def build_taste_section(file_store: FileStore, taste_prior: TastePrior) -> ContextSection:
	"""Return what one taste prior shows the model."""
	if taste_prior.kind == TastePriorKind.IMAGE and taste_prior.asset is not None:
		return ContextSection(
			heading=taste_prior.name,
			body="",
			image=await read_image(file_store, taste_prior.asset),
		)

	lead = "Follow this skill.\n\n" if taste_prior.kind == TastePriorKind.SKILL else ""
	return ContextSection(heading=taste_prior.name, body=f"{lead}{taste_prior.text_content or ''}")


async def load_prompt_context(
	session: AsyncSession,
	file_store: FileStore,
	project_id: uuid.UUID,
	parent_node: Node | None,
	disabled_taste_prior_ids: list[uuid.UUID],
) -> PromptContext:
	"""Gather the context for a generation.

	Args:
		session: Database session to read from.
		file_store: Where uploaded images are kept.
		project_id: Project whose priors apply.
		parent_node: Node the generation continues from, if any.
		disabled_taste_prior_ids: Taste priors the project's interface switches off.

	Returns:
		The taste priors left on, the enabled priors, the taste reasons picked on the branch, and
		the image of the parent node when it is an uploaded one.
	"""
	# Collect the taste priors that are switched on.
	taste_result = await session.execute(
		select(TastePrior)
		.where(TastePrior.id.not_in(disabled_taste_prior_ids))
		.options(selectinload(TastePrior.asset))
		.order_by(TastePrior.created_at)
	)
	taste_sections = [
		await build_taste_section(file_store, taste_prior) for taste_prior in taste_result.scalars()
	]

	# Collect the project's priors that are switched on.
	prior_result = await session.execute(
		select(Prior)
		.where(Prior.project_id == project_id, Prior.is_enabled.is_(True))
		.options(
			selectinload(Prior.library_item).selectinload(LibraryItem.asset),
			selectinload(Prior.library_item)
			.selectinload(LibraryItem.node)
			.selectinload(Node.image_asset),
		)
		.order_by(Prior.created_at)
	)
	prior_sections: list[ContextSection] = []
	for prior in prior_result.scalars():
		section = await build_prior_section(session, file_store, prior)
		if section is not None:
			prior_sections.append(section)

	# Collect the taste reasons the director picked on the way to the parent node.
	ancestors = await list_ancestors(session, parent_node.id if parent_node else None)
	taste_reasons = [ancestor.taste_reason for ancestor in ancestors if ancestor.taste_reason]

	# Attach the director's own edit when continuing from an uploaded node.
	edited_render: PromptImage | None = None
	if parent_node is not None and parent_node.image_asset_id is not None:
		asset = await session.get(Asset, parent_node.image_asset_id)
		if asset is not None:
			edited_render = await read_image(file_store, asset)

	return PromptContext(
		taste_sections=taste_sections,
		prior_sections=prior_sections,
		taste_reasons=taste_reasons,
		edited_render=edited_render,
	)
