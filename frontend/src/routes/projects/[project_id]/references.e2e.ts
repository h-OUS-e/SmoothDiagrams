import { expect, test, type Page } from '@playwright/test';
import type { LibraryItemDetail, PriorDetail } from '../../../lib/api/api_types.ts';
import {
	backend_url,
	build_finished_node,
	mock_piece_with_node,
	mock_project_routes,
	project
} from '../../../../e2e/mock_backend.ts';
import { sample_diagram_source } from '../../../../e2e/sample_diagram.ts';

const created_at = '2026-11-21T10:00:00Z';

const library_item: LibraryItemDetail = {
	id: '55555555-5555-4555-8555-555555555555',
	kind: 'image',
	name: 'Moodboard',
	asset_id: '66666666-6666-4666-8666-666666666666',
	node_id: null,
	created_at,
	render_svg: null
};

const prior: PriorDetail = {
	id: '77777777-7777-4777-8777-777777777777',
	project_id: project.id,
	name: 'Moodboard',
	text_content: null,
	library_item,
	prior_note: '',
	is_enabled: true,
	created_at
};

// Answer the library with one image item, and accept it as a prior of the project.
async function mock_library_with_one_image(page: Page) {
	await page.route(`${backend_url}/library?*`, (route) => route.fulfill({ json: [library_item] }));
	await page.route(`${backend_url}/assets/**`, (route) =>
		route.fulfill({
			contentType: 'image/svg+xml',
			body: '<svg xmlns="http://www.w3.org/2000/svg"/>'
		})
	);
	await page.route(`${backend_url}/projects/${project.id}/priors`, (route) =>
		route.fulfill({ json: route.request().method() === 'POST' ? prior : [] })
	);
}

test.beforeEach(async ({ page }) => {
	await mock_project_routes(page);
});

test('uses a library item as a prior and stores the note written on it', async ({ page }) => {
	await mock_library_with_one_image(page);
	await page.route(`${backend_url}/priors/${prior.id}`, (route) => route.fulfill({ json: prior }));
	await page.goto(`/projects/${project.id}`);

	// Clicking the item in the library adds it to the project's priors.
	const add_request = page.waitForRequest(
		(request) => request.method() === 'POST' && request.url().endsWith('/priors')
	);
	await page.getByRole('button', { name: 'Use Moodboard as a prior' }).click();
	expect((await add_request).postDataJSON()).toEqual({ library_item_id: library_item.id });
	await expect(page.getByRole('heading', { name: 'Moodboard' })).toBeVisible();
	await expect(
		page.getByRole('button', { name: 'Moodboard, already a prior of this project' })
	).toBeVisible();

	// A note typed on the prior is stored once typing pauses.
	const note_request = page.waitForRequest((request) => request.method() === 'PATCH');
	await page.getByLabel('Prior note').fill('Take the palette');
	expect((await note_request).postDataJSON()).toEqual({ prior_note: 'Take the palette' });
});

test('takes a library item dragged into the priors', async ({ page }) => {
	await mock_library_with_one_image(page);
	await page.goto(`/projects/${project.id}`);

	await page
		.getByRole('button', { name: 'Use Moodboard as a prior' })
		.dragTo(page.getByRole('complementary', { name: 'Priors' }));

	await expect(page.getByRole('heading', { name: 'Moodboard' })).toBeVisible();
});

test('asks why the director continued from a node and stores the reason they pick', async ({
	page
}) => {
	// Load a node that continues another and still has unanswered candidate reasons.
	const child_node = build_finished_node(sample_diagram_source, {
		parent_node_id: '88888888-8888-4888-8888-888888888888',
		taste_reason_candidates: ['I like the bare rings', 'I like the empty space']
	});
	await mock_piece_with_node(page, child_node);
	await page.route(`${backend_url}/nodes/${child_node.id}/taste_reason`, (route) =>
		route.fulfill({ json: child_node })
	);
	await page.goto(`/projects/${project.id}`);

	const reason_request = page.waitForRequest((request) => request.url().endsWith('/taste_reason'));
	await page.getByRole('button', { name: 'I like the empty space' }).click();

	expect((await reason_request).postDataJSON()).toEqual({ taste_reason: 'I like the empty space' });
	await expect(page.getByRole('region', { name: 'Taste reason' })).toBeHidden();
});
