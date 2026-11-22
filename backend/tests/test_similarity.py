"""Tests for sorting the library by visual similarity."""

import io
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from huggingface_hub import try_to_load_from_cache
from PIL import Image

from smooth_diagrams.settings import Settings
from smooth_diagrams.similarity.embedder import ClipEmbedder, input_size, prepare_image
from smooth_diagrams.similarity.rasterize import rasterize_svg, render_width
from tests import test_generations
from tests.color_embedder import ColorEmbedder
from tests.scripted_provider import ScriptedProvider
from tests.test_generations import create_piece
from tests.test_references import generate_node

red = (220, 30, 30)
orange = (230, 140, 20)
blue = (20, 40, 220)

red_svg = (
	'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 3">'
	'<rect width="4" height="3" fill="rgb(220, 30, 30)"/></svg>'
)


def build_png(color: tuple[int, int, int], size: tuple[int, int] = (8, 6)) -> bytes:
	"""Return a PNG filled with one color."""
	content = io.BytesIO()
	Image.new("RGB", size, color).save(content, format="PNG")
	return content.getvalue()


def add_image(client: TestClient, name: str, content: bytes) -> dict[str, Any]:
	"""Upload an image into the library under a name and return its item."""
	response = client.post("/library/images", files={"file": (f"{name}.png", content, "image/png")})
	assert response.status_code == 201
	return response.json()


def list_similar(client: TestClient, item: dict[str, Any]) -> list[str]:
	"""Return the names of the library's items, ordered by likeness to one of them."""
	response = client.get("/library", params={"sort": "similarity", "similar_to": item["id"]})
	assert response.status_code == 200, response.text
	return [similar_item["name"] for similar_item in response.json()]


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def test_library_is_sorted_by_likeness_to_one_item(client: TestClient) -> None:
	red_item = add_image(client, "red", build_png(red))
	blue_item = add_image(client, "blue", build_png(blue))
	add_image(client, "orange", build_png(orange))

	assert list_similar(client, red_item) == ["red", "orange", "blue"]
	assert list_similar(client, blue_item)[0] == "blue"


def test_embeddings_are_computed_once_per_item(
	client: TestClient, color_embedder: ColorEmbedder
) -> None:
	red_item = add_image(client, "red", build_png(red))
	add_image(client, "blue", build_png(blue))

	list_similar(client, red_item)
	list_similar(client, red_item)
	assert color_embedder.embedded_counts == [2]

	# Only an item that joined since then is computed.
	add_image(client, "orange", build_png(orange))
	list_similar(client, red_item)
	assert color_embedder.embedded_counts == [2, 1]


def test_embeddings_of_another_model_are_computed_again(
	client: TestClient, color_embedder: ColorEmbedder
) -> None:
	red_item = add_image(client, "red", build_png(red))
	add_image(client, "blue", build_png(blue))
	list_similar(client, red_item)

	color_embedder.model_name = "another_model"
	list_similar(client, red_item)

	assert color_embedder.embedded_counts == [2, 2]


def test_node_is_compared_by_the_render_of_its_newest_step(
	client: TestClient,
	scripted_provider: ScriptedProvider,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	# Have the generation's steps render as a red diagram.
	monkeypatch.setattr(test_generations, "rendered_svg", red_svg)
	node = generate_node(client, scripted_provider, create_piece(client))
	node_item = client.post("/library/nodes", json={"node_id": node["id"]}).json()
	add_image(client, "blue", build_png(blue))
	add_image(client, "orange", build_png(orange))

	assert list_similar(client, node_item) == [node_item["name"], "orange", "blue"]


def test_item_with_an_unreadable_image_comes_last(client: TestClient) -> None:
	# The upload check reads only the first bytes, so a broken file can get into the library.
	broken_png = build_png(red)[:24]
	red_item = add_image(client, "red", build_png(red))
	broken_item = add_image(client, "broken", broken_png)
	add_image(client, "blue", build_png(blue))

	assert list_similar(client, red_item) == ["red", "blue", "broken"]

	# Nothing can be compared with an item that cannot be looked at.
	response = client.get(
		"/library", params={"sort": "similarity", "similar_to": broken_item["id"]}
	)
	assert response.status_code == 409


def test_sorting_by_similarity_needs_a_known_item(client: TestClient) -> None:
	add_image(client, "red", build_png(red))
	unknown_id = "00000000-0000-0000-0000-000000000000"

	assert client.get("/library", params={"sort": "similarity"}).status_code == 422
	response = client.get("/library", params={"sort": "similarity", "similar_to": unknown_id})
	assert response.status_code == 404


def test_model_that_cannot_be_loaded_is_reported(
	client: TestClient, color_embedder: ColorEmbedder
) -> None:
	red_item = add_image(client, "red", build_png(red))
	color_embedder.is_available = False

	response = client.get("/library", params={"sort": "similarity", "similar_to": red_item["id"]})

	assert response.status_code == 503
	assert "could not be loaded" in response.json()["detail"]

	# The other orders need no model and keep working.
	assert client.get("/library").status_code == 200


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def test_render_is_drawn_as_a_png() -> None:
	with Image.open(io.BytesIO(rasterize_svg(red_svg))) as image:
		assert image.format == "PNG"
		assert image.size == (render_width, render_width * 3 // 4)
		assert image.convert("RGB").getpixel((10, 10)) == red


def test_markup_that_is_not_svg_cannot_be_drawn() -> None:
	with pytest.raises(ValueError):
		rasterize_svg("not markup")


def test_image_is_fitted_whole_onto_a_white_square() -> None:
	# A wide image keeps its sides and gets paper above and below.
	prepared = prepare_image(build_png(blue, size=(400, 100)))

	assert prepared.shape == (3, input_size, input_size)
	paper = prepare_image(build_png((255, 255, 255)))
	assert np.allclose(prepared[:, 0, :], paper[:, 0, :])
	assert not np.allclose(prepared[:, input_size // 2, 0], paper[:, input_size // 2, 0])


def test_clip_embeddings_tell_images_apart() -> None:
	# Run the real model only where it was downloaded before, so tests never fetch it.
	settings = Settings()
	cached_path = try_to_load_from_cache(
		settings.similarity_model_repository,
		settings.similarity_model_file,
		revision=settings.similarity_model_revision,
	)
	if not isinstance(cached_path, str):
		pytest.skip("The similarity model is not in the Hugging Face cache.")

	embedder = ClipEmbedder(
		settings.similarity_model_repository,
		settings.similarity_model_file,
		settings.similarity_model_revision,
	)
	red_embedding, dark_red_embedding, blue_embedding = embedder.embed(
		[build_png(red), build_png((150, 20, 20)), build_png(blue)]
	)

	assert red_embedding.shape == (512,)
	assert np.isclose(np.linalg.norm(red_embedding), 1.0, atol=1e-4)
	assert red_embedding @ dark_red_embedding > red_embedding @ blue_embedding
