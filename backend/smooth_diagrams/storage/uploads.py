"""Check uploaded images and store them as assets."""

import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from smooth_diagrams.database.models import Asset
from smooth_diagrams.storage.file_store import FileStore

# Image types a model can look at, with the file extension each is stored under.
image_extensions = {
	"image/png": ".png",
	"image/jpeg": ".jpg",
	"image/gif": ".gif",
	"image/webp": ".webp",
}


def detect_image_type(content: bytes) -> str | None:
	"""Return the media type of image bytes, read from their first bytes, or None."""
	if content.startswith(b"\x89PNG\r\n\x1a\n"):
		return "image/png"
	if content.startswith(b"\xff\xd8\xff"):
		return "image/jpeg"
	if content.startswith((b"GIF87a", b"GIF89a")):
		return "image/gif"
	if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
		return "image/webp"
	return None


async def store_image(
	upload: UploadFile, file_store: FileStore, session: AsyncSession, byte_limit: int
) -> Asset:
	"""Store an uploaded image and return its asset, not yet committed.

	Args:
		upload: The file the director uploaded.
		file_store: Where the bytes are kept.
		session: Database session the asset is added to.
		byte_limit: Largest file accepted, in bytes.

	Returns:
		The new asset; the caller commits it together with whatever refers to it.

	Raises:
		HTTPException: The file is too large or is not a PNG, JPEG, GIF, or WebP image.
	"""
	# Read one byte past the limit, so an oversized file is noticed without loading all of it.
	content = await upload.read(byte_limit + 1)
	if len(content) > byte_limit:
		raise HTTPException(
			status.HTTP_413_CONTENT_TOO_LARGE,
			f"The image is larger than {byte_limit // 1_000_000} MB.",
		)

	# Trust the bytes rather than the type the browser claims.
	media_type = detect_image_type(content)
	if media_type is None:
		raise HTTPException(
			status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
			"Only PNG, JPEG, GIF, and WebP images can be used.",
		)

	asset_id = uuid.uuid4()
	storage_key = f"{asset_id.hex}{image_extensions[media_type]}"
	await file_store.save(storage_key, content)

	asset = Asset(
		id=asset_id,
		file_name=upload.filename or "image",
		media_type=media_type,
		storage_key=storage_key,
		byte_size=len(content),
	)
	session.add(asset)
	return asset
