import { readFile } from 'node:fs/promises';
import { expect, test, type Download, type Page } from '@playwright/test';
import type { ExportDetail, ExportInput } from '../../../lib/api/api_types.ts';
import {
	backend_url,
	build_finished_node,
	mock_piece_with_node,
	mock_project_routes,
	project
} from '../../../../e2e/mock_backend.ts';
import { sample_diagram_source } from '../../../../e2e/sample_diagram.ts';

const node = build_finished_node(sample_diagram_source);

// Bytes every PNG file starts with.
const png_signature = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

// Answer a remembered export with what was sent, the way the server does.
async function mock_export_route(page: Page) {
	await page.route(`${backend_url}/nodes/${node.id}/exports`, (route) => {
		const export_input = route.request().postDataJSON() as ExportInput;
		const node_export: ExportDetail = {
			...export_input,
			id: '99999999-9999-4999-8999-99999999999a',
			node_id: node.id,
			created_at: '2026-11-22T10:00:00Z'
		};
		return route.fulfill({ status: 201, json: node_export });
	});
}

// Export with the settings on screen and return the saved file and what the server was told.
async function export_and_wait(page: Page): Promise<{ download: Download; sent: ExportInput }> {
	const download_started = page.waitForEvent('download');
	const export_request = page.waitForRequest((request) => request.url().endsWith('/exports'));
	await page.getByRole('button', { name: 'Export', exact: true }).click();

	const download = await download_started;
	return { download, sent: (await export_request).postDataJSON() as ExportInput };
}

test.beforeEach(async ({ page }) => {
	await mock_project_routes(page);
	await mock_piece_with_node(page, node);
	await mock_export_route(page);
	await page.goto(`/projects/${project.id}`);

	// Wait for the diagram, which is what an export is made from.
	const diagram = page.frameLocator('iframe[title="Diagram"]').first();
	await expect(diagram.locator('circle')).toHaveCount(3);
});

test('exports a Svelte component whose defaults are the values on screen', async ({ page }) => {
	// Change a number and a color, so the export has both kinds of value to carry.
	await page.getByRole('slider', { name: 'Rings' }).fill('7');
	await page.getByRole('tab', { name: 'Effects' }).click();
	await page.getByLabel('Ink').fill('#d3262e');
	await page.getByRole('tab', { name: 'Export' }).click();
	await page.getByLabel('Format').selectOption('svelte');
	await expect(page.getByText('Saves Piece1.svelte.')).toBeVisible();

	const { download, sent } = await export_and_wait(page);

	// The file is the step's source with the changed defaults, and nothing else touched.
	const exported_source = await readFile(await download.path(), 'utf-8');
	expect(download.suggestedFilename()).toBe('Piece1.svelte');
	expect(exported_source).toBe(
		sample_diagram_source
			.replace('ring_count = 3', 'ring_count = 7')
			.replace("ink = '#1b1d21'", "ink = '#d3262e'")
	);

	expect(sent).toEqual({
		step_id: node.steps[0].id,
		format: 'svelte',
		parameter_values: { ring_count: 7, ink: '#d3262e' },
		animation_time: 0,
		pixel_width: null,
		pixel_height: null
	});

	// The export is listed, and the node is marked as exported in the tree.
	await expect(page.getByRole('heading', { name: 'Exports of this node' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Rings (exported)' })).toBeVisible();
});

test('exports a PNG at the width the director sets', async ({ page }) => {
	await page.getByRole('tab', { name: 'Export' }).click();

	// A new image is offered at twice the diagram's own size.
	await expect(page.getByLabel('Width in pixels')).toHaveValue('800');
	await page.getByLabel('File name').fill('Launch post');
	await page.getByLabel('Width in pixels').fill('1080');
	await expect(page.getByText('Saves launch_post.png, 1080 by 810 pixels.')).toBeVisible();

	const { download, sent } = await export_and_wait(page);

	// The file is a PNG whose header states the size asked for.
	const image = await readFile(await download.path());
	expect([...image.subarray(0, 8)]).toEqual(png_signature);
	expect([image.readUInt32BE(16), image.readUInt32BE(20)]).toEqual([1080, 810]);
	expect(sent).toMatchObject({ format: 'png', pixel_width: 1080, pixel_height: 810 });
	await expect(page.getByText('PNG, 1080 by 810', { exact: true })).toBeVisible();
});

test('exports the diagram as it looks now as an SVG file', async ({ page }) => {
	await page.getByLabel('Animation time').fill('2');
	await page.getByRole('tab', { name: 'Export' }).click();
	await page.getByLabel('Format').selectOption('svg');

	const { download, sent } = await export_and_wait(page);

	// The markup stands on its own: it states its size and carries the diagram's styles.
	const markup = await readFile(await download.path(), 'utf-8');
	expect(download.suggestedFilename()).toBe('piece_1.svg');
	expect(markup).toContain('width="400"');
	expect(markup).toContain('stroke-width: 2');
	expect(markup.match(/<circle/g)).toHaveLength(3);
	expect(markup).toContain('r="22"');
	expect(sent).toMatchObject({ format: 'svg', animation_time: 2, pixel_width: null });
});

test('refuses an image wider than a browser can draw', async ({ page }) => {
	await page.getByRole('tab', { name: 'Export' }).click();
	await page.getByLabel('Width in pixels').fill('20000');

	await expect(page.getByRole('alert')).toHaveText(
		'An image can be at most 16384 pixels on a side.'
	);
	await expect(page.getByRole('button', { name: 'Export', exact: true })).toBeDisabled();
});
