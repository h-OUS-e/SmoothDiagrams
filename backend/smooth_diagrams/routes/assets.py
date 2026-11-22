"""Route that serves uploaded images."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status

from smooth_diagrams.database.models import Asset
from smooth_diagrams.routes.dependencies import FileStoreDependency, SessionDependency

router = APIRouter()


@router.get("/assets/{asset_id}/file")
async def get_asset_file(
	asset_id: uuid.UUID, session: SessionDependency, file_store: FileStoreDependency
) -> Response:
	"""Return the bytes of an uploaded image."""
	asset = await session.get(Asset, asset_id)
	if asset is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")

	# An asset never changes, so the browser may keep it; it must not guess another type for it.
	return Response(
		await file_store.read(asset.storage_key),
		media_type=asset.media_type,
		headers={
			"cache-control": "private, max-age=31536000, immutable",
			"x-content-type-options": "nosniff",
		},
	)
