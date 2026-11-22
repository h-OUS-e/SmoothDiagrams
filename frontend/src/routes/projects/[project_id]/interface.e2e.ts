import { expect, test, type Request } from '@playwright/test';
import type { InterfaceSettings, InterfaceState } from '../../../lib/api/api_types.ts';
import {
	backend_url,
	interface_state,
	mock_generation_socket,
	mock_project_routes,
	project
} from '../../../../e2e/mock_backend.ts';

// Return the settings a request stored in the project's interface.
function read_saved_settings(request: Request): InterfaceSettings {
	return request.postDataJSON() as InterfaceSettings;
}

// Return whether a request stores the project's interface.
function saves_interface(request: Request): boolean {
	return request.method() === 'PUT' && request.url().endsWith('/interface');
}

test.beforeEach(async ({ page }) => {
	await mock_project_routes(page);
});

test('stores the interface before a generation starts, so the server draws with it', async ({
	page
}) => {
	const generation_started = mock_generation_socket(page);
	await page.goto(`/projects/${project.id}`);

	// Move a prompt control and start at once, before the pause that normally precedes a save.
	const save_request = page.waitForRequest(saves_interface);
	await page.getByRole('slider', { name: 'Novelty' }).fill('85');
	await page.getByLabel('Start this piece').fill('Rings');
	await page.getByRole('button', { name: 'Draw' }).click();

	const novelty = read_saved_settings(await save_request).prompt_controls.find(
		(control) => control.id === 'novelty'
	);
	expect(novelty?.value).toBe(85);
	expect((await generation_started).start).toEqual({
		type: 'start',
		piece_id: project.pieces[0].id,
		parent_step_id: null,
		parent_node_id: null,
		prompt: 'Rings'
	});
});

test('lets the director rewrite the direction and add a prompt control', async ({ page }) => {
	await page.goto(`/projects/${project.id}`);
	await page.getByRole('tab', { name: 'Interface' }).click();

	// A direction written for the project is stored in its prompt templates.
	const direction_request = page.waitForRequest(saves_interface);
	await page
		.getByLabel('Direction for every diagram of this project')
		.fill('Postcards for a coffee roaster.');
	expect(read_saved_settings(await direction_request).prompt_templates.direction).toBe(
		'Postcards for a coffee roaster.'
	);

	// A new control appears under Prompting and is stored with a starting range.
	await page.getByText('Add a prompt control').click();
	const add_form = page.locator('form', { hasText: 'Add control' });
	await add_form.getByLabel('Label').fill('Warmth');
	await add_form.getByLabel('Instruction').fill('Warmth is {value} out of 100.');
	const control_request = page.waitForRequest(saves_interface);
	await add_form.getByRole('button', { name: 'Add control' }).click();

	await expect(page.getByRole('slider', { name: 'Warmth' })).toBeVisible();
	expect(read_saved_settings(await control_request).prompt_controls.at(-1)).toMatchObject({
		id: 'warmth',
		kind: 'slider',
		instruction: 'Warmth is {value} out of 100.',
		value: 50
	});
});

test('restores an earlier version of the interface', async ({ page }) => {
	// Load an interface whose second version is in use and whose first made a node.
	const first_version = { ...interface_state.versions[0], node_count: 1, is_current: false };
	const second_version = {
		...first_version,
		id: '99999999-9999-4999-8999-999999999992',
		version_number: 2,
		node_count: 0,
		is_current: true
	};
	const second_state: InterfaceState = {
		...interface_state,
		current_version_id: second_version.id,
		version_number: 2,
		settings: { ...interface_state.settings, is_step_by_step: false },
		versions: [second_version, first_version]
	};
	const restored_state: InterfaceState = {
		...interface_state,
		versions: [
			{ ...second_version, is_current: false },
			{ ...first_version, is_current: true }
		]
	};
	await page.route(`${backend_url}/projects/${project.id}/interface`, (route) =>
		route.fulfill({ json: second_state })
	);
	await page.route(`${backend_url}/projects/${project.id}/interface/restore`, (route) =>
		route.fulfill({ json: restored_state })
	);
	await page.goto(`/projects/${project.id}`);

	await expect(page.getByText('Interface version 2')).toBeVisible();
	await expect(page.getByLabel('Draw step by step')).not.toBeChecked();

	// Restoring the first version brings its settings back on screen.
	await page.getByRole('tab', { name: 'Interface' }).click();
	const restore_request = page.waitForRequest((request) => request.url().endsWith('/restore'));
	await page.getByRole('button', { name: 'Restore' }).click();

	expect((await restore_request).postDataJSON()).toEqual({
		interface_version_id: first_version.id
	});
	await expect(page.getByText('Interface version 1')).toBeVisible();
	await expect(page.getByLabel('Draw step by step')).toBeChecked();
});
