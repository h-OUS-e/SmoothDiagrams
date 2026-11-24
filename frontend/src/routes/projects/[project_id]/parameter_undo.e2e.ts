import { expect, test, type Page } from '@playwright/test';
import type { ParameterValues } from '../../../lib/features/diagram_viewer/diagram_parameters.ts';
import {
	backend_url,
	build_finished_node,
	mock_piece_with_node,
	mock_project_routes,
	project
} from '../../../../e2e/mock_backend.ts';
import { sample_diagram_source } from '../../../../e2e/sample_diagram.ts';

const node = build_finished_node(sample_diagram_source);

// Answer stored parameter values with the node, the way the server does.
async function mock_parameter_values_route(page: Page) {
	await page.route(`${backend_url}/nodes/${node.id}/parameter_values`, (route) =>
		route.fulfill({ json: node })
	);
}

// Wait until the page stores exactly these parameter values.
function wait_for_stored_values(page: Page, parameter_values: ParameterValues) {
	return page.waitForRequest(
		(request) =>
			request.url().endsWith(`/nodes/${node.id}/parameter_values`) &&
			JSON.stringify(request.postDataJSON()) === JSON.stringify({ parameter_values })
	);
}

test.beforeEach(async ({ page }) => {
	await mock_project_routes(page);
	await mock_piece_with_node(page, node);
	await mock_parameter_values_route(page);
	await page.goto(`/projects/${project.id}`);

	// Wait for the diagram, whose exposed parameters are what gets undone.
	const diagram = page.frameLocator('iframe[title="Diagram"]').first();
	await expect(diagram.locator('circle')).toHaveCount(3);
});

test('undoes and redoes parameter changes across both parameter tabs', async ({ page }) => {
	const diagram = page.frameLocator('iframe[title="Diagram"]').first();
	const undo_button = page.getByRole('button', { name: 'Undo parameter change' });
	const redo_button = page.getByRole('button', { name: 'Redo parameter change' });
	await expect(undo_button).toBeDisabled();

	// Change a structure parameter twice, then a styling parameter on the Effects tab.
	await page.getByRole('slider', { name: 'Rings' }).fill('7');
	await page.getByRole('slider', { name: 'Rings' }).fill('5');
	await page.getByRole('tab', { name: 'Effects' }).click();
	await page.getByLabel('Ink').fill('#d3262e');
	await expect(diagram.locator('circle').first()).toHaveAttribute('stroke', '#d3262e');

	// Undo every change from the keyboard, newest first, which stores the values it returns to.
	await page.keyboard.press('Control+z');
	await expect(diagram.locator('circle').first()).toHaveAttribute('stroke', '#1b1d21');
	await page.keyboard.press('Control+z');
	await expect(diagram.locator('circle')).toHaveCount(7);
	const stored_defaults = wait_for_stored_values(page, {});
	await page.keyboard.press('Control+z');
	await expect(diagram.locator('circle')).toHaveCount(3);
	await stored_defaults;
	await expect(undo_button).toBeDisabled();

	// Redo with both redo shortcuts, then with the button.
	await page.keyboard.press('Control+y');
	await expect(diagram.locator('circle')).toHaveCount(7);
	await page.keyboard.press('Control+Shift+z');
	await expect(diagram.locator('circle')).toHaveCount(5);
	await redo_button.click();
	await expect(diagram.locator('circle').first()).toHaveAttribute('stroke', '#d3262e');
	await expect(redo_button).toBeDisabled();

	// A new change after an undo leaves nothing to redo.
	await undo_button.click();
	await expect(redo_button).toBeEnabled();
	await page.getByLabel('Ink').fill('#2e6bd3');
	await expect(redo_button).toBeDisabled();
});

test('leaves undo inside a text box to the text box', async ({ page }) => {
	const diagram = page.frameLocator('iframe[title="Diagram"]').first();
	await page.getByRole('slider', { name: 'Rings' }).fill('7');
	await expect(diagram.locator('circle')).toHaveCount(7);

	// Undo while typing a prompt, which must not take back the parameter change.
	const prompt_box = page.getByLabel('Continue from step 1');
	await prompt_box.fill('Add a label');
	await prompt_box.press('Control+z');
	await expect(diagram.locator('circle')).toHaveCount(7);
	await expect(page.getByRole('button', { name: 'Undo parameter change' })).toBeEnabled();
});
