"""Turn images into embeddings: vectors that lie close together for images that look alike."""

import io
import threading
from typing import Protocol

import numpy as np
import onnxruntime
from huggingface_hub import hf_hub_download
from PIL import Image

# Side of the square the model looks at, in pixels.
input_size = 224

# Color put behind transparent images and around ones that are not square: the app's paper.
background_color = (255, 255, 255)

# Per-channel mean and spread of the images CLIP was trained on, which its input is scaled by.
clip_mean = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
clip_deviation = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)

# Images embedded in one run of the model, which bounds the memory a large library needs.
batch_size = 16


class EmbedderUnavailableError(Exception):
	"""The embedding model could not be loaded, for example because its download failed."""


class ImageUnreadableError(Exception):
	"""Bytes handed over as an image could not be read as one."""


class ImageEmbedder(Protocol):
	"""Computes embeddings of images."""

	# Names the model, so embeddings made by another model are recognized as out of date.
	model_name: str

	def embed(self, images: list[bytes]) -> np.ndarray:
		"""Return one embedding of length one per image, as rows. Blocking.

		Raises:
			EmbedderUnavailableError: The model could not be loaded.
			ImageUnreadableError: One of the images could not be read.
		"""
		...


def prepare_image(content: bytes) -> np.ndarray:
	"""Return an image as the array CLIP takes: channels first, scaled the way it was trained.

	The whole image is fitted onto a white square, because the usual center crop would cut the
	sides off a wide diagram.

	Raises:
		ImageUnreadableError: The bytes are not an image Pillow can read, or it is too large.
	"""
	try:
		with Image.open(io.BytesIO(content)) as opened:
			image = opened.convert("RGBA")
	except (OSError, ValueError, Image.DecompressionBombError) as error:
		raise ImageUnreadableError(str(error)) from error

	# Flatten transparency onto paper, since the model has no notion of see-through.
	flattened = Image.new("RGBA", image.size, (*background_color, 255))
	flattened.alpha_composite(image)

	# Fit the image inside the square, keeping its proportions.
	scale = input_size / max(flattened.size)
	fitted_size = (
		max(1, round(flattened.width * scale)),
		max(1, round(flattened.height * scale)),
	)
	fitted = flattened.convert("RGB").resize(fitted_size, Image.Resampling.BICUBIC)
	square = Image.new("RGB", (input_size, input_size), background_color)
	square.paste(fitted, ((input_size - fitted.width) // 2, (input_size - fitted.height) // 2))

	pixels = np.asarray(square, dtype=np.float32) / 255.0
	return ((pixels - clip_mean) / clip_deviation).transpose(2, 0, 1)


def normalize_rows(vectors: np.ndarray) -> np.ndarray:
	"""Return vectors scaled to length one, so their dot product is their cosine similarity."""
	lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
	return (vectors / np.maximum(lengths, 1e-12)).astype(np.float32)


class ClipEmbedder:
	"""Embeds images with the image half of CLIP, run locally on the processor."""

	def __init__(self, repository: str, file_name: str, revision: str) -> None:
		self.model_name = f"{repository}/{file_name}@{revision}"
		self._repository = repository
		self._file_name = file_name
		self._revision = revision
		self._session: onnxruntime.InferenceSession | None = None
		self._load_lock = threading.Lock()

	def _load(self) -> onnxruntime.InferenceSession:
		"""Return the model, downloading it into the Hugging Face cache on first use."""
		with self._load_lock:
			if self._session is None:
				try:
					model_path = hf_hub_download(
						self._repository, self._file_name, revision=self._revision
					)
					self._session = onnxruntime.InferenceSession(
						model_path, providers=["CPUExecutionProvider"]
					)
				except Exception as error:
					raise EmbedderUnavailableError(
						f"The similarity model could not be loaded: {error}"
					) from error
			return self._session

	def embed(self, images: list[bytes]) -> np.ndarray:
		"""Return one embedding of length one per image, as rows. Blocking."""
		session = self._load()
		input_name = session.get_inputs()[0].name
		output_name = session.get_outputs()[0].name

		embeddings: list[np.ndarray] = []
		for start in range(0, len(images), batch_size):
			batch = np.stack([prepare_image(image) for image in images[start : start + batch_size]])
			embeddings.append(session.run([output_name], {input_name: batch})[0])
		return normalize_rows(np.concatenate(embeddings))
