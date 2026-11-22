"""Tests for the library, priors, taste priors, uploaded nodes, and taste reasons."""

import base64
from typing import Any

from fastapi.testclient import TestClient

from smooth_diagrams.providers.base import SourceTools
from tests.scripted_provider import ScriptedProvider
from tests.test_generations import Director, create_piece, source_a, source_b

# The smallest valid PNG: one transparent pixel.
png_bytes = base64.b64decode(
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def upload(client: TestClient, path: str, **fields: str) -> Any:
	"""Upload the test image to a route and return the response."""
	return client.post(path, files={"file": ("moodboard.png", png_bytes, "image/png")}, data=fields)


def generate_node(
	client: TestClient, scripted_provider: ScriptedProvider, piece_id: str, **start_fields: Any
) -> dict[str, Any]:
	"""Run a generation that draws two steps and return the node it created."""

	async def turn(source_tools: SourceTools) -> None:
		await source_tools.write_source("Circle first", source_a)
		await source_tools.write_source("Then a rect", source_b)

	scripted_provider.turns.append(turn)
	with client.websocket_connect("/generations") as websocket:
		director = Director(websocket, piece_id, **start_fields)
		director.receive_until("generation_ended")
	return client.get(f"/nodes/{director.events[0]['node']['id']}").json()


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def test_uploaded_image_joins_the_library_and_is_served(client: TestClient) -> None:
	item = upload(client, "/library/images").json()

	assert item["kind"] == "image"
	assert item["name"] == "moodboard"

	response = client.get(f"/assets/{item['asset_id']}/file")
	assert response.content == png_bytes
	assert response.headers["content-type"] == "image/png"


def test_file_that_is_not_an_image_is_refused(client: TestClient) -> None:
	response = client.post(
		"/library/images", files={"file": ("notes.png", b"<svg></svg>", "image/png")}
	)
	assert response.status_code == 415


def test_image_over_the_size_limit_is_refused(client: TestClient) -> None:
	oversized = png_bytes + b"\0" * 5_000_000
	response = client.post("/library/images", files={"file": ("big.png", oversized, "image/png")})
	assert response.status_code == 413


def test_node_is_sent_to_the_library_once(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	node = generate_node(client, scripted_provider, create_piece(client))

	first = client.post("/library/nodes", json={"node_id": node["id"]}).json()
	second = client.post("/library/nodes", json={"node_id": node["id"]}).json()

	assert first["id"] == second["id"]
	assert first["kind"] == "node"
	assert first["render_svg"] is not None
	assert len(client.get("/library").json()) == 1


def test_library_sorts_by_name_or_newest_first(client: TestClient) -> None:
	upload(client, "/library/images", name="Zebra")
	upload(client, "/library/images", name="Apple")

	assert [item["name"] for item in client.get("/library").json()] == ["Apple", "Zebra"]
	by_name = client.get("/library", params={"sort": "name"}).json()
	assert [item["name"] for item in by_name] == ["Apple", "Zebra"]


def test_removing_a_library_item_removes_its_file_and_priors(client: TestClient) -> None:
	project = client.post("/projects", json={"name": "Postcards"}).json()
	item = upload(client, "/library/images").json()
	client.post(f"/projects/{project['id']}/priors", json={"library_item_id": item["id"]})

	assert client.delete(f"/library/{item['id']}").status_code == 204

	assert client.get("/library").json() == []
	assert client.get(f"/projects/{project['id']}/priors").json() == []
	assert client.get(f"/assets/{item['asset_id']}/file").status_code == 404


# ---------------------------------------------------------------------------
# Priors and taste priors
# ---------------------------------------------------------------------------


def test_library_item_becomes_a_prior_once_and_takes_a_note(client: TestClient) -> None:
	project = client.post("/projects", json={"name": "Postcards"}).json()
	item = upload(client, "/library/images", name="Moodboard").json()
	priors_path = f"/projects/{project['id']}/priors"

	prior = client.post(priors_path, json={"library_item_id": item["id"]}).json()
	again = client.post(priors_path, json={"library_item_id": item["id"]}).json()
	assert prior["id"] == again["id"]
	assert prior["name"] == "Moodboard"
	assert prior["is_enabled"] is True

	changed = client.patch(
		f"/priors/{prior['id']}", json={"prior_note": "Take the palette", "is_enabled": False}
	).json()
	assert changed["prior_note"] == "Take the palette"
	assert changed["is_enabled"] is False

	assert client.delete(f"/priors/{prior['id']}").status_code == 204
	assert client.get(priors_path).json() == []
	assert len(client.get("/library").json()) == 1


def test_text_prior_needs_a_name_and_text(client: TestClient) -> None:
	project = client.post("/projects", json={"name": "Postcards"}).json()
	priors_path = f"/projects/{project['id']}/priors"

	assert client.post(priors_path, json={"name": "Brief"}).status_code == 422
	prior = client.post(priors_path, json={"name": "Brief", "text_content": "For roasters"}).json()
	assert prior["library_item"] is None
	assert prior["text_content"] == "For roasters"


def test_taste_priors_can_be_text_skill_or_image(client: TestClient) -> None:
	text = client.post(
		"/taste_priors", json={"kind": "text", "name": "House style", "text_content": "Few colors"}
	).json()
	client.post(
		"/taste_priors", json={"kind": "skill", "name": "Anti slop", "text_content": "No gradients"}
	)
	image = upload(client, "/taste_priors/images").json()
	assert image["kind"] == "image"

	renamed = client.patch(f"/taste_priors/{text['id']}", json={"name": "House rules"}).json()
	assert renamed["name"] == "House rules"
	assert [taste_prior["kind"] for taste_prior in client.get("/taste_priors").json()] == [
		"text",
		"skill",
		"image",
	]

	assert client.delete(f"/taste_priors/{image['id']}").status_code == 204
	assert client.get(f"/assets/{image['asset_id']}/file").status_code == 404


def test_generation_is_told_the_enabled_priors_and_taste(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	project = client.post("/projects", json={"name": "Postcards"}).json()
	piece_id = project["pieces"][0]["id"]
	priors_path = f"/projects/{project['id']}/priors"

	# A past diagram, an image, and a brief as priors; one of two taste priors switched off
	# in the interface of the project.
	past_node = generate_node(client, scripted_provider, piece_id)
	node_item = client.post("/library/nodes", json={"node_id": past_node["id"]}).json()
	image_item = upload(client, "/library/images", name="Moodboard").json()
	client.post(priors_path, json={"library_item_id": node_item["id"]})
	image_prior = client.post(priors_path, json={"library_item_id": image_item["id"]}).json()
	client.patch(f"/priors/{image_prior['id']}", json={"prior_note": "Take the palette"})
	client.post(priors_path, json={"name": "Brief", "text_content": "For coffee roasters"})
	client.post(
		"/taste_priors", json={"kind": "skill", "name": "Anti slop", "text_content": "No gradients"}
	)
	hidden = client.post(
		"/taste_priors", json={"kind": "text", "name": "Old rule", "text_content": "Use neon"}
	).json()
	interface = client.get(f"/projects/{project['id']}/interface").json()["settings"]
	interface["disabled_taste_prior_ids"] = [hidden["id"]]
	client.put(f"/projects/{project['id']}/interface", json=interface)

	generate_node(client, scripted_provider, piece_id)
	prompt = scripted_provider.prompts[-1]

	assert "No gradients" in prompt and "Use neon" not in prompt
	assert "For coffee roasters" in prompt
	assert "Take the palette" in prompt and "Attached as image 1." in prompt
	assert source_b in prompt and "Then a rect" in prompt
	assert prompt.index("The taste of this director") < prompt.index("Priors the director chose")
	assert prompt.rstrip().endswith("Draw a diagram")
	assert [image.data for image in scripted_provider.images[-1]] == [png_bytes]


# ---------------------------------------------------------------------------
# Uploaded nodes
# ---------------------------------------------------------------------------


def test_uploaded_node_hangs_under_the_step_it_edits(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	piece_id = create_piece(client)
	node = generate_node(client, scripted_provider, piece_id)
	last_step = node["steps"][-1]

	uploaded = upload(
		client, f"/pieces/{piece_id}/uploaded_nodes", parent_step_id=last_step["id"]
	).json()

	assert uploaded["kind"] == "uploaded"
	assert uploaded["status"] == "finished"
	assert uploaded["parent_node_id"] == node["id"]
	assert uploaded["steps"] == []
	assert uploaded["image_asset_id"] is not None

	summaries = client.get(f"/pieces/{piece_id}").json()["nodes"]
	assert summaries[-1]["image_asset_id"] == uploaded["image_asset_id"]


def test_continuing_from_an_uploaded_node_shows_the_model_the_edit(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	piece_id = create_piece(client)
	node = generate_node(client, scripted_provider, piece_id)
	uploaded = upload(
		client, f"/pieces/{piece_id}/uploaded_nodes", parent_step_id=node["steps"][-1]["id"]
	).json()

	child = generate_node(client, scripted_provider, piece_id, parent_node_id=uploaded["id"])

	# The model gets the edited image, plus the source of the step the image is an edit of.
	prompt = scripted_provider.prompts[-1]
	assert "The edit the director made by hand" in prompt and "image 1" in prompt
	assert source_b in prompt
	assert [image.data for image in scripted_provider.images[-1]] == [png_bytes]
	assert child["parent_node_id"] == uploaded["id"]
	assert child["parent_step_id"] is None


# ---------------------------------------------------------------------------
# Taste reasons
# ---------------------------------------------------------------------------


def test_taste_reasons_are_offered_stored_and_fed_to_later_generations(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	piece_id = create_piece(client)
	parent = generate_node(client, scripted_provider, piece_id)
	first_step, last_step = parent["steps"]
	child = generate_node(client, scripted_provider, piece_id, parent_step_id=first_step["id"])

	# The agent is told what was picked, and its three candidates are stored unpicked.
	scripted_provider.completion = (
		'Here you go:\n["I like the bare circle", "I like the empty space", "I like the weight"]'
	)
	offered = client.post(f"/nodes/{child['id']}/taste_reason_candidates").json()
	assert offered["candidates"][0] == "I like the bare circle"
	agent_prompt = scripted_provider.completion_prompts[-1]
	assert "Circle first" in agent_prompt and "step 1 of 2" in agent_prompt
	stored = client.get(f"/nodes/{child['id']}").json()
	assert len(stored["taste_reason_candidates"]) == 3
	assert stored["taste_reason"] is None

	# An unpicked candidate is not fed forward; a picked reason is.
	grandchild = generate_node(
		client, scripted_provider, piece_id, parent_step_id=child["steps"][-1]["id"]
	)
	assert "I like the bare circle" not in scripted_provider.prompts[-1]

	client.patch(
		f"/nodes/{child['id']}/taste_reason", json={"taste_reason": "I like the bare circle"}
	)
	generate_node(client, scripted_provider, piece_id, parent_step_id=grandchild["steps"][-1]["id"])
	assert "- I like the bare circle" in scripted_provider.prompts[-1]

	# A branch that does not pass through the node with the reason is not told it.
	generate_node(client, scripted_provider, piece_id, parent_step_id=last_step["id"])
	assert "I like the bare circle" not in scripted_provider.prompts[-1]


def test_root_node_has_no_pick_to_explain(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	node = generate_node(client, scripted_provider, create_piece(client))
	assert client.post(f"/nodes/{node['id']}/taste_reason_candidates").status_code == 409


def test_unusable_answer_from_the_agent_is_reported(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	piece_id = create_piece(client)
	parent = generate_node(client, scripted_provider, piece_id)
	child = generate_node(
		client, scripted_provider, piece_id, parent_step_id=parent["steps"][-1]["id"]
	)

	scripted_provider.completion = "I cannot say."
	assert client.post(f"/nodes/{child['id']}/taste_reason_candidates").status_code == 502
