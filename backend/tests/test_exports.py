"""Tests for remembering the exports of a node."""

from typing import Any

from fastapi.testclient import TestClient

from tests.scripted_provider import ScriptedProvider
from tests.test_generations import create_piece
from tests.test_references import generate_node


def export_step(client: TestClient, node: dict[str, Any], **fields: Any) -> Any:
	"""Export the newest step of a node and return the response."""
	export_input = {"step_id": node["steps"][-1]["id"], "format": "svg", **fields}
	return client.post(f"/nodes/{node['id']}/exports", json=export_input)


def test_export_is_remembered_on_its_node(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	piece_id = create_piece(client)
	node = generate_node(client, scripted_provider, piece_id)

	response = export_step(
		client,
		node,
		format="png",
		parameter_values={"ring_count": 9, "ink": "#d3262e"},
		animation_time=1.5,
		pixel_width=2000,
		pixel_height=1500,
	)

	assert response.status_code == 201
	export = response.json()
	assert export["format"] == "png"
	assert export["step_id"] == node["steps"][-1]["id"]
	assert export["parameter_values"] == {"ring_count": 9, "ink": "#d3262e"}
	assert export["animation_time"] == 1.5
	assert (export["pixel_width"], export["pixel_height"]) == (2000, 1500)

	# The node lists its exports, and the piece's tree counts them.
	assert client.get(f"/nodes/{node['id']}").json()["exports"] == [export]
	[summary] = client.get(f"/pieces/{piece_id}").json()["nodes"]
	assert summary["export_count"] == 1


def test_exports_are_listed_oldest_first(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	node = generate_node(client, scripted_provider, create_piece(client))

	export_step(client, node, format="svelte")
	export_step(client, node, format="svg")

	exports = client.get(f"/nodes/{node['id']}").json()["exports"]
	assert [export["format"] for export in exports] == ["svelte", "svg"]
	assert exports[0]["pixel_width"] is None


def test_new_node_has_no_exports(client: TestClient, scripted_provider: ScriptedProvider) -> None:
	piece_id = create_piece(client)
	node = generate_node(client, scripted_provider, piece_id)

	assert node["exports"] == []
	assert client.get(f"/pieces/{piece_id}").json()["nodes"][0]["export_count"] == 0


def test_pixel_size_must_fit_the_format(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	node = generate_node(client, scripted_provider, create_piece(client))

	# An image needs both sides, and a format without pixels takes neither.
	assert export_step(client, node, format="jpeg").status_code == 422
	assert export_step(client, node, format="png", pixel_width=800).status_code == 422
	assert (
		export_step(client, node, format="svg", pixel_width=800, pixel_height=600).status_code
		== 422
	)
	assert export_step(client, node, format="gif").status_code == 422

	too_wide = export_step(client, node, format="png", pixel_width=20000, pixel_height=600)
	assert too_wide.status_code == 422


def test_step_of_another_node_cannot_be_exported(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	piece_id = create_piece(client)
	node = generate_node(client, scripted_provider, piece_id)
	other_node = generate_node(client, scripted_provider, piece_id)

	response = export_step(client, node, step_id=other_node["steps"][-1]["id"])

	assert response.status_code == 404
	assert client.get(f"/nodes/{node['id']}").json()["exports"] == []


def test_export_of_an_unknown_node_is_not_found(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	node = generate_node(client, scripted_provider, create_piece(client))
	unknown_node = {**node, "id": "00000000-0000-0000-0000-000000000000"}

	assert export_step(client, unknown_node).status_code == 404
