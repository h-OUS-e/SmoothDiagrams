"""Routes for taste priors, which apply to every project."""

import uuid
from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from smooth_diagrams.database.models import Asset, TastePrior, TastePriorKind
from smooth_diagrams.routes.dependencies import (
	FileStoreDependency,
	SessionDependency,
	SettingsDependency,
)
from smooth_diagrams.schemas import TastePriorChanges, TastePriorDetail, TastePriorInput
from smooth_diagrams.storage.uploads import store_image

router = APIRouter()


@router.get("/taste_priors")
async def list_taste_priors(session: SessionDependency) -> list[TastePriorDetail]:
	"""Return every taste prior, oldest first."""
	result = await session.execute(select(TastePrior).order_by(TastePrior.created_at))
	return [TastePriorDetail.model_validate(taste_prior) for taste_prior in result.scalars()]


@router.post("/taste_priors", status_code=status.HTTP_201_CREATED)
async def add_text_taste_prior(
	taste_prior_input: TastePriorInput, session: SessionDependency
) -> TastePriorDetail:
	"""Add a taste prior made of text: plain taste notes, or a skill document."""
	if taste_prior_input.kind == TastePriorKind.IMAGE:
		raise HTTPException(
			status.HTTP_422_UNPROCESSABLE_CONTENT, "Upload an image taste prior as a file."
		)

	taste_prior = TastePrior(
		kind=taste_prior_input.kind,
		name=taste_prior_input.name.strip(),
		text_content=taste_prior_input.text_content,
	)
	session.add(taste_prior)
	await session.commit()
	return TastePriorDetail.model_validate(taste_prior)


@router.post("/taste_priors/images", status_code=status.HTTP_201_CREATED)
async def add_image_taste_prior(
	file: UploadFile,
	session: SessionDependency,
	file_store: FileStoreDependency,
	settings: SettingsDependency,
	name: Annotated[str | None, Form(max_length=200)] = None,
) -> TastePriorDetail:
	"""Add an uploaded image as a taste prior, named after its file unless a name is given."""
	asset = await store_image(file, file_store, session, settings.image_byte_limit)
	taste_prior = TastePrior(
		kind=TastePriorKind.IMAGE,
		name=(name or "").strip() or PurePath(asset.file_name).stem,
		asset_id=asset.id,
	)
	session.add(taste_prior)
	await session.commit()
	return TastePriorDetail.model_validate(taste_prior)


@router.patch("/taste_priors/{taste_prior_id}")
async def change_taste_prior(
	taste_prior_id: uuid.UUID, changes: TastePriorChanges, session: SessionDependency
) -> TastePriorDetail:
	"""Switch a taste prior on or off, or change its name or text."""
	taste_prior = await session.get(TastePrior, taste_prior_id)
	if taste_prior is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Taste prior not found")

	# Apply only the fields that were sent.
	for field_name, value in changes.model_dump(exclude_unset=True).items():
		if value is not None:
			setattr(taste_prior, field_name, value)
	await session.commit()
	return TastePriorDetail.model_validate(taste_prior)


@router.delete("/taste_priors/{taste_prior_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_taste_prior(
	taste_prior_id: uuid.UUID, session: SessionDependency, file_store: FileStoreDependency
) -> None:
	"""Remove a taste prior, along with its image file if it has one."""
	taste_prior = await session.get(TastePrior, taste_prior_id)
	if taste_prior is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Taste prior not found")

	asset = await session.get(Asset, taste_prior.asset_id) if taste_prior.asset_id else None
	await session.delete(taste_prior)
	if asset is not None:
		await session.delete(asset)
	await session.commit()

	# Remove the file last, so a failed commit never leaves a row without its file.
	if asset is not None:
		await file_store.delete(asset.storage_key)
