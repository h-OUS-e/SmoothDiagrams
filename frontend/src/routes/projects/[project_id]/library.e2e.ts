import { expect, test, type Page } from '@playwright/test';
import type { LibraryItemDetail } from '../../../lib/api/api_types.ts';
import { backend_url, mock_project_routes, project } from '../../../../e2e/mock_backend.ts';

// Return an image item of the library; the name also makes its id.
function build_item(name: string, id_digit: number): LibraryItemDetail {
	return {
		id: `55555555-5555-4555-8555-55555555555${id_digit}`,
		kind: 'image',
		name,
		asset_id: `66666666-6666-4666-8666-66666666666${id_digit}`,
		node_id: null,
		created_at: '2026-11-21T10:00:00Z',
		render_svg: null
	};
}

const poster = build_item('Poster', 1);
const sketch = build_item('Sketch', 2);
const photo = build_item('Photo', 3);
const newest_first = [poster, sketch, photo];

// Answer the library newest first, or with the compared item first and the rest turned around.
async function mock_library(page: Page) {
	await page.route(`${backend_url}/library?*`, (route) => {
		const query = new URL(route.request().url()).searchParams;
		if (query.get('sort') !== 'similarity') return route.fulfill({ json: newest_first });

		const compared_item = newest_first.find((item) => item.id === query.get('similar_to'));
		const others = newest_first.filter((item) => item !== compared_item).reverse();
		return route.fulfill({ json: [compared_item, ...others] });
	});
	await page.route(`${backend_url}/assets/**`, (route) =>
		route.fulfill({
			contentType: 'image/svg+xml',
			body: '<svg xmlns="http://www.w3.org/2000/svg"/>'
		})
	);
}

// Return the names of the library's items in the order they are shown.
async function read_item_names(page: Page): Promise<string[]> {
	const labels = await page
		.getByRole('region', { name: 'Library' })
		.getByRole('button', { name: /^Use .* as a prior$/ })
		.evaluateAll((tiles) => tiles.map((tile) => tile.getAttribute('aria-label') ?? ''));
	return labels.map((label) => label.replace(/^Use (.*) as a prior$/, '$1'));
}

test.beforeEach(async ({ page }) => {
	await mock_project_routes(page);
});

test('sorts the library by similarity to the item the director picks', async ({ page }) => {
	await mock_library(page);
	await page.goto(`/projects/${project.id}`);
	await expect.poll(() => read_item_names(page)).toEqual(['Poster', 'Sketch', 'Photo']);

	// Picking an item puts it first, marks it, and selects the similarity order.
	const compare_sketch = page.getByRole('button', {
		name: 'Sort the library by similarity to Sketch'
	});
	await compare_sketch.click();
	await expect(page.getByRole('tab', { name: 'Similar' })).toHaveAttribute('aria-selected', 'true');
	await expect(compare_sketch).toHaveAttribute('aria-pressed', 'true');
	await expect.poll(() => read_item_names(page)).toEqual(['Sketch', 'Photo', 'Poster']);

	// Going back to another order and returning compares with the same item again.
	await page.getByRole('tab', { name: 'Newest' }).click();
	await expect(compare_sketch).toHaveAttribute('aria-pressed', 'false');
	await expect.poll(() => read_item_names(page)).toEqual(['Poster', 'Sketch', 'Photo']);
	await page.getByRole('tab', { name: 'Similar' }).click();
	await expect(compare_sketch).toHaveAttribute('aria-pressed', 'true');
});

test('compares with the first item when the director has not picked one', async ({ page }) => {
	await mock_library(page);
	await page.goto(`/projects/${project.id}`);

	const similarity_request = page.waitForRequest((request) => request.url().includes('similar_to'));
	await page.getByRole('tab', { name: 'Similar' }).click();

	expect(new URL((await similarity_request).url()).searchParams.get('similar_to')).toBe(poster.id);
	await expect(
		page.getByRole('button', { name: 'Sort the library by similarity to Poster' })
	).toHaveAttribute('aria-pressed', 'true');
	await expect.poll(() => read_item_names(page)).toEqual(['Poster', 'Photo', 'Sketch']);
});

test('keeps the order on screen when the comparison fails', async ({ page }) => {
	// Answer every similarity request with the error of a model that could not be loaded.
	await page.route(`${backend_url}/library?*`, (route) =>
		route.request().url().includes('similarity')
			? route.fulfill({
					status: 503,
					json: { detail: 'The similarity model could not be loaded: offline' }
				})
			: route.fulfill({ json: newest_first })
	);
	await page.goto(`/projects/${project.id}`);

	await page.getByRole('tab', { name: 'Similar' }).click();

	await expect(page.getByRole('alert')).toHaveText(
		'The similarity model could not be loaded: offline'
	);
	await expect(page.getByRole('tab', { name: 'Newest' })).toHaveAttribute('aria-selected', 'true');
	await expect.poll(() => read_item_names(page)).toEqual(['Poster', 'Sketch', 'Photo']);
});
