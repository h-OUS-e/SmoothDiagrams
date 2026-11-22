"""An image embedder that needs no model, so tests can sort a library by similarity."""

import io

import numpy as np
from PIL import Image

from smooth_diagrams.similarity.embedder import (
	EmbedderUnavailableError,
	ImageUnreadableError,
	normalize_rows,
)


class ColorEmbedder:
	"""Embeds an image as its average color, which is enough to tell plain test images apart."""

	def __init__(self) -> None:
		self.model_name = "average_color"

		# Tests switch this off to stand in for a model that failed to download.
		self.is_available = True

		# Number of images in each call, so tests can see what was computed again.
		self.embedded_counts: list[int] = []

	def embed(self, images: list[bytes]) -> np.ndarray:
		"""Return the average color of each image as a vector of length one."""
		if not self.is_available:
			raise EmbedderUnavailableError("The similarity model could not be loaded: offline")

		colors = []
		for content in images:
			try:
				with Image.open(io.BytesIO(content)) as opened:
					pixels = np.asarray(opened.convert("RGB"), dtype=np.float32)
			except OSError as error:
				raise ImageUnreadableError(str(error)) from error

			# Lift every channel a little, so black still points somewhere.
			colors.append(pixels.reshape(-1, 3).mean(axis=0) + 1.0)

		self.embedded_counts.append(len(images))
		return normalize_rows(np.stack(colors))
