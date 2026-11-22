import { expect, test } from '@playwright/test';
import {
	build_step,
	generating_node,
	mock_generation_socket,
	mock_project_routes,
	project
} from '../../../../e2e/mock_backend.ts';
import { broken_diagram_source, sample_diagram_source } from '../../../../e2e/sample_diagram.ts';

test.beforeEach(async ({ page }) => {
	await mock_project_routes(page);
});

test('renders a proposed step, saves it, and exposes its parameters', async ({ page }) => {
	const generation_started = mock_generation_socket(page);
	await page.goto(`/projects/${project.id}`);

	// Start a generation from the prompt box.
	await page.getByLabel('Start this piece').fill('Rings');
	await page.getByRole('button', { name: 'Draw' }).click();
	const generation = await generation_started;
	expect(generation.start).toMatchObject({ prompt: 'Rings', parent_step_id: null });

	// Propose a step and read the verdict the page sends back.
	generation.send({ type: 'node_created', node: generating_node });
	generation.send({
		type: 'step_proposed',
		step_token: 'token_1',
		source: sample_diagram_source,
		step_reasoning: 'Reasoning of step 1'
	});
	const outcome = await generation.next_command();
	if (outcome.type !== 'step_outcome' || outcome.render_svg === null) {
		throw new Error(`Expected a rendered step outcome, got ${JSON.stringify(outcome)}`);
	}
	expect(outcome.ok).toBe(true);
	expect(outcome.render_svg).toContain('<circle');

	// Save the step and end the generation.
	generation.send({
		type: 'step_saved',
		step: build_step(0, sample_diagram_source, outcome.render_svg)
	});
	generation.send({ type: 'generation_ended', status: 'finished', message: null });

	// The step shows in the viewer with the diagram's default of three rings.
	const diagram = page.frameLocator('iframe[title="Diagram"]').first();
	await expect(page.getByRole('button', { name: 'Step 1' })).toBeVisible();
	await expect(page.getByText('Reasoning of step 1')).toBeVisible();
	await expect(diagram.locator('circle')).toHaveCount(3);

	// Moving an exposed parameter's control changes the diagram straight away.
	await page.getByRole('slider', { name: 'Rings' }).fill('7');
	await expect(diagram.locator('circle')).toHaveCount(7);

	// The animation clock reaches the diagram through its time prop.
	await page.getByLabel('Animation time').fill('2');
	await expect(diagram.locator('circle').first()).toHaveAttribute('r', '22');
});

test('reports a step that does not compile so the model can repair it', async ({ page }) => {
	const generation_started = mock_generation_socket(page);
	await page.goto(`/projects/${project.id}`);

	await page.getByLabel('Start this piece').fill('Rings');
	await page.getByRole('button', { name: 'Draw' }).click();
	const generation = await generation_started;

	generation.send({ type: 'node_created', node: generating_node });
	generation.send({
		type: 'step_proposed',
		step_token: 'token_1',
		source: broken_diagram_source,
		step_reasoning: 'Reasoning of step 1'
	});

	const outcome = await generation.next_command();
	expect(outcome).toMatchObject({ type: 'step_outcome', step_token: 'token_1', ok: false });
	expect(outcome.type === 'step_outcome' && outcome.message).toContain('compile stage');
});

test('names each model with its version and warns about one billed outside the plan', async ({
	page
}) => {
	const generation_started = mock_generation_socket(page);
	await page.goto(`/projects/${project.id}`);

	const model = page.getByLabel('Model');
	await expect(model).toHaveValue('claude-opus-5-5');
	await expect(model.locator('option')).toHaveText(['Claude Opus 5.5', 'Claude Fable 5.2']);
	await expect(page.getByText('Can be billed to usage credits.')).toBeHidden();

	// Choosing the model shows its note and sends its exact id with the next generation.
	await model.selectOption('claude-fable-5-2');
	await expect(page.getByText('Can be billed to usage credits.')).toBeVisible();

	await page.getByLabel('Start this piece').fill('Rings');
	await page.getByRole('button', { name: 'Draw' }).click();
	expect((await generation_started).start.model).toBe('claude-fable-5-2');
});

test('sends steering commands while a generation runs', async ({ page }) => {
	const generation_started = mock_generation_socket(page);
	await page.goto(`/projects/${project.id}`);

	await page.getByLabel('Start this piece').fill('Rings');
	await page.getByRole('button', { name: 'Draw' }).click();
	const generation = await generation_started;
	generation.send({ type: 'node_created', node: generating_node });

	// Pause and resume follow what the server confirms.
	await page.getByRole('button', { name: 'Pause' }).click();
	expect(await generation.next_command()).toEqual({ type: 'pause' });
	generation.send({ type: 'paused' });
	await page.getByRole('button', { name: 'Resume' }).click();
	expect(await generation.next_command()).toEqual({ type: 'resume' });
	generation.send({ type: 'resumed' });

	// A typed direction becomes a redirect.
	await page.getByLabel('Steer the drawing').fill('Make it blue');
	await page.getByRole('button', { name: 'Redirect' }).click();
	expect(await generation.next_command()).toEqual({ type: 'redirect', prompt: 'Make it blue' });

	await page.getByRole('button', { name: 'Stop' }).click();
	expect(await generation.next_command()).toEqual({ type: 'stop' });
	generation.send({ type: 'generation_ended', status: 'stopped', message: null });
	await expect(page.getByRole('button', { name: 'Draw' })).toBeVisible();
});
