"""Tests for interface versions: saving, freezing, restoring, carrying forward, and their effect."""

from typing import Any

from fastapi.testclient import TestClient

from tests.scripted_provider import ScriptedProvider
from tests.test_references import generate_node


def create_project(client: TestClient, **fields: Any) -> dict[str, Any]:
	"""Create a project and return it."""
	return client.post("/projects", json={"name": "Postcards", **fields}).json()


def read_interface(client: TestClient, project_id: str) -> dict[str, Any]:
	"""Return a project's interface state."""
	return client.get(f"/projects/{project_id}/interface").json()


def save_interface(client: TestClient, project_id: str, **changes: Any) -> dict[str, Any]:
	"""Change some of a project's interface settings and return the new interface state."""
	settings = {**read_interface(client, project_id)["settings"], **changes}
	response = client.put(f"/projects/{project_id}/interface", json=settings)
	assert response.status_code == 200, response.text
	return response.json()


def find_control(settings: dict[str, Any], control_id: str) -> dict[str, Any]:
	"""Return one prompt control of some settings."""
	return next(control for control in settings["prompt_controls"] if control["id"] == control_id)


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


def test_project_starts_with_a_first_version_of_the_defaults(client: TestClient) -> None:
	interface = read_interface(client, create_project(client)["id"])

	assert interface["version_number"] == 1
	assert interface["settings"]["model"] == "claude-opus-5-5"
	assert interface["settings"]["is_step_by_step"] is True
	assert [control["id"] for control in interface["settings"]["prompt_controls"]] == [
		"ratio",
		"media_type",
		"novelty",
	]
	assert "Working in steps" in interface["settings"]["prompt_templates"]["step_by_step"]
	assert [version["is_current"] for version in interface["versions"]] == [True]


def test_version_changes_in_place_until_it_made_a_node(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	project = create_project(client)
	piece_id = project["pieces"][0]["id"]

	# Changes to a version that made nothing stay in that version.
	save_interface(client, project["id"], is_step_by_step=False)
	unused = save_interface(client, project["id"], offers_taste_reasons=False)
	assert unused["version_number"] == 1
	assert len(unused["versions"]) == 1

	# A node records the version that made it, which is frozen from then on.
	node = generate_node(client, scripted_provider, piece_id)
	assert node["interface_version_id"] == unused["current_version_id"]
	assert node["is_step_by_step"] is False

	changed = save_interface(client, project["id"], is_step_by_step=True)
	assert changed["version_number"] == 2
	assert [(v["version_number"], v["node_count"]) for v in changed["versions"]] == [(2, 0), (1, 1)]

	# Saving the same settings again adds nothing.
	assert save_interface(client, project["id"])["version_number"] == 2


def test_earlier_version_can_be_restored_and_stays_as_it_was(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	project = create_project(client)
	first = read_interface(client, project["id"])
	generate_node(client, scripted_provider, project["pieces"][0]["id"])
	save_interface(client, project["id"], is_step_by_step=False)

	restored = client.post(
		f"/projects/{project['id']}/interface/restore",
		json={"interface_version_id": first["current_version_id"]},
	).json()
	assert restored["version_number"] == 1
	assert restored["settings"]["is_step_by_step"] is True

	# Changing the restored version, which made a node, continues in a new version.
	changed = save_interface(client, project["id"], offers_taste_reasons=False)
	assert changed["version_number"] == 3
	assert len(changed["versions"]) == 3


def test_version_of_another_project_cannot_be_restored(client: TestClient) -> None:
	other_version_id = read_interface(client, create_project(client)["id"])["current_version_id"]
	project = create_project(client)

	response = client.post(
		f"/projects/{project['id']}/interface/restore",
		json={"interface_version_id": other_version_id},
	)
	assert response.status_code == 404


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_settings_that_cannot_work_are_refused(client: TestClient) -> None:
	project_id = create_project(client)["id"]
	settings = read_interface(client, project_id)["settings"]
	path = f"/projects/{project_id}/interface"

	# A model the app does not offer.
	assert client.put(path, json={**settings, "model": "some-other-model"}).status_code == 422

	# A slider whose value lies outside its range.
	novelty = {**find_control(settings, "novelty"), "value": 400}
	out_of_range = {**settings, "prompt_controls": [novelty]}
	assert client.put(path, json=out_of_range).status_code == 422

	# Two prompt controls with the same id.
	doubled = {**settings, "prompt_controls": [*settings["prompt_controls"], novelty]}
	assert client.put(path, json=doubled).status_code == 422


# ---------------------------------------------------------------------------
# Effect on generations
# ---------------------------------------------------------------------------


def test_generation_follows_the_interface(
	client: TestClient, scripted_provider: ScriptedProvider
) -> None:
	project = create_project(client)
	settings = read_interface(client, project["id"])["settings"]

	# Rewrite the direction, set a slider, and add a toggle that is off and one that is on.
	templates = {**settings["prompt_templates"], "direction": "Postcards for a coffee roaster."}
	toggle = {"kind": "toggle", "instruction": "Leave room for a stamp."}
	controls = [
		{**find_control(settings, "ratio"), "value": "7:5 (postcard)"},
		{**find_control(settings, "novelty"), "value": 85},
		{**toggle, "id": "stamp", "label": "Stamp", "value": True},
		{**toggle, "id": "bleed", "label": "Bleed", "instruction": "Add bleed.", "value": False},
	]
	save_interface(
		client,
		project["id"],
		model="claude-sonnet-5-5",
		is_step_by_step=False,
		prompt_templates=templates,
		prompt_controls=controls,
	)

	generate_node(client, scripted_provider, project["pieces"][0]["id"])
	system_prompt = scripted_provider.system_prompts[-1]

	assert scripted_provider.models[-1] == "claude-sonnet-5-5"
	assert "Working in one pass" in system_prompt and "Working in steps" not in system_prompt
	assert "Postcards for a coffee roaster." in system_prompt
	assert "ratio is 7:5 (postcard)" in system_prompt
	assert "Novelty is 85 out of 100" in system_prompt
	assert "Leave room for a stamp." in system_prompt
	assert "Add bleed." not in system_prompt


# ---------------------------------------------------------------------------
# Carrying forward
# ---------------------------------------------------------------------------


def test_new_project_starts_from_a_copy_of_any_interface_version(client: TestClient) -> None:
	source_project = create_project(client)
	source = save_interface(client, source_project["id"], is_step_by_step=False)

	# The version is offered as a source, and the new project copies its settings.
	[offered] = client.get("/interface_versions").json()
	assert offered["id"] == source["current_version_id"]
	assert offered["project_name"] == "Postcards"

	new_project = create_project(client, interface_version_id=source["current_version_id"])
	copied = read_interface(client, new_project["id"])
	assert copied["version_number"] == 1
	assert copied["settings"] == source["settings"]

	# The copy and its source no longer affect each other.
	save_interface(client, new_project["id"], is_step_by_step=True)
	assert read_interface(client, source_project["id"])["settings"]["is_step_by_step"] is False
	changed_source = save_interface(client, source_project["id"], offers_taste_reasons=False)
	assert changed_source["version_number"] == 2


def test_project_cannot_start_from_an_unknown_interface_version(client: TestClient) -> None:
	response = client.post(
		"/projects",
		json={"name": "Postcards", "interface_version_id": "00000000-0000-0000-0000-000000000000"},
	)
	assert response.status_code == 404
