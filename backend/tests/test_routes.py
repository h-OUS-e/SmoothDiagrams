"""Tests for the HTTP routes and the origin guard."""

from fastapi.testclient import TestClient


def test_new_project_starts_with_one_piece(client: TestClient) -> None:
	response = client.post("/projects", json={"name": "  Postcards  "})

	assert response.status_code == 201
	project = response.json()
	assert project["name"] == "Postcards"
	assert [piece["name"] for piece in project["pieces"]] == ["Piece 1"]


def test_projects_are_listed_with_piece_count(client: TestClient) -> None:
	project = client.post("/projects", json={"name": "Postcards"}).json()
	client.post(f"/projects/{project['id']}/pieces", json={"name": "Piece 2"})

	[summary] = client.get("/projects").json()
	assert summary["piece_count"] == 2
	assert summary["cover_svg"] is None


def test_project_and_piece_can_be_renamed(client: TestClient) -> None:
	project = client.post("/projects", json={"name": "Postcards"}).json()
	piece_id = project["pieces"][0]["id"]

	renamed_project = client.patch(f"/projects/{project['id']}", json={"name": "November"}).json()
	renamed_piece = client.patch(f"/pieces/{piece_id}", json={"name": "Week one"}).json()

	assert renamed_project["name"] == "November"
	assert renamed_piece["name"] == "Week one"


def test_empty_name_is_refused(client: TestClient) -> None:
	assert client.post("/projects", json={"name": ""}).status_code == 422


def test_unknown_ids_return_not_found(client: TestClient) -> None:
	unknown_id = "00000000-0000-0000-0000-000000000000"
	assert client.get(f"/projects/{unknown_id}").status_code == 404
	assert client.get(f"/pieces/{unknown_id}").status_code == 404
	assert client.get(f"/nodes/{unknown_id}").status_code == 404


def test_model_catalog_names_versions_and_a_default(client: TestClient) -> None:
	catalog = client.get("/models").json()

	model_ids = [model["id"] for model in catalog["models"]]
	assert catalog["default_model"] in model_ids
	assert "claude-fable-5-2" in model_ids
	assert {model["label"] for model in catalog["models"]} >= {
		"Claude Opus 5.5",
		"Claude Fable 5.2",
	}

	# Only the model that can be billed outside the plan carries a note.
	notes = {model["id"]: model["note"] for model in catalog["models"]}
	assert "usage credits" in notes["claude-fable-5-2"]
	assert notes["claude-opus-5-5"] is None


def test_other_origins_cannot_change_state(client: TestClient) -> None:
	headers = {"origin": "https://example.com"}

	assert client.post("/projects", json={"name": "Postcards"}, headers=headers).status_code == 403
	assert client.get("/projects", headers=headers).status_code == 200


def test_frontend_can_change_state_from_any_local_port(client: TestClient) -> None:
	# The dev server takes another port when its usual one is busy.
	for origin in ("http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:4173"):
		response = client.post("/projects", json={"name": "Postcards"}, headers={"origin": origin})
		assert response.status_code == 201
		assert response.headers["access-control-allow-origin"] == origin


def test_browser_may_use_every_method_the_frontend_sends(client: TestClient) -> None:
	# A browser asks first before a request that is not a plain form post.
	for method in ("POST", "PUT", "PATCH", "DELETE"):
		response = client.options(
			"/projects",
			headers={
				"origin": "http://localhost:5173",
				"access-control-request-method": method,
				"access-control-request-headers": "content-type",
			},
		)
		assert response.status_code == 200, method
		assert method in response.headers["access-control-allow-methods"]


def test_lookalike_origins_are_refused(client: TestClient) -> None:
	for origin in ("http://localhost.example.com:5173", "https://example.com/localhost:5173"):
		response = client.post("/projects", json={"name": "Postcards"}, headers={"origin": origin})
		assert response.status_code == 403
