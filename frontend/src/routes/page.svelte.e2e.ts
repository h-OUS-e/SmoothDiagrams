import { expect, test } from '@playwright/test';
import { backend_url, mock_project_routes, project } from '../../e2e/mock_backend.ts';

test('lists projects and opens a new one', async ({ page }) => {
	await mock_project_routes(page);
	await page.goto('/');

	await expect(page.getByRole('link', { name: /November postcards/ })).toBeVisible();

	await page.getByLabel('Name of the new project').fill('November postcards');
	await page.getByRole('button', { name: 'Create project' }).click();

	await expect(page).toHaveURL(new RegExp(`/projects/${project.id}`));
	await expect(page.getByRole('heading', { name: 'November postcards' })).toBeVisible();
});

test('explains how to start the local server when it cannot be reached', async ({ page }) => {
	await page.route(`${backend_url}/**`, (route) => route.abort());
	await page.goto('/');

	await expect(
		page.getByRole('heading', { name: 'The local server is not running' })
	).toBeVisible();
});
