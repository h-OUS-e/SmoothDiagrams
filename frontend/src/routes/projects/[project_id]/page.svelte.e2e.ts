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

test('shows the styles a later step changes, not the ones of the step before', async ({ page }) => {
	const thicker_source = sample_diagram_source.replace('stroke-width: 2;', 'stroke-width: 7;');
	const generation_started = mock_generation_socket(page);
	await page.goto(`/projects/${project.id}`);

	await page.getByLabel('Start this piece').fill('Rings');
	await page.getByRole('button', { name: 'Draw' }).click();
	const generation = await generation_started;
	generation.send({ type: 'node_created', node: generating_node });

	// Render two steps one after the other, the second with a restyled ring.
	const sources = [sample_diagram_source, thicker_source];
	const render_svgs: string[] = [];
	for (const [step_index, source] of sources.entries()) {
		generation.send({
			type: 'step_proposed',
			step_token: `token_${step_index}`,
			source,
			step_reasoning: `Reasoning of step ${step_index + 1}`
		});
		const outcome = await generation.next_command();
		if (outcome.type !== 'step_outcome' || outcome.render_svg === null) {
			throw new Error(`Expected a rendered step outcome, got ${JSON.stringify(outcome)}`);
		}
		render_svgs.push(outcome.render_svg);
		generation.send({
			type: 'step_saved',
			step: build_step(step_index, source, outcome.render_svg)
		});
	}
	generation.send({ type: 'generation_ended', status: 'finished', message: null });

	// The stored render of each step carries that step's own styles.
	expect(render_svgs[0]).toContain('stroke-width: 2');
	expect(render_svgs[1]).toContain('stroke-width: 7');
	expect(render_svgs[1]).not.toContain('stroke-width: 2');

	// So does the viewer, for the newest step and for an earlier one selected again.
	const ring = page.frameLocator('iframe[title="Diagram"]').first().locator('circle').first();
	await expect(ring).toHaveCSS('stroke-width', '7px');
	await page.getByRole('button', { name: 'Step 1' }).click();
	await expect(ring).toHaveCSS('stroke-width', '2px');
});

test('keeps a new generation running when the socket of the one before closes late', async ({
	page
}) => {
	const first_started = mock_generation_socket(page);
	await page.goto(`/projects/${project.id}`);

	// End a first generation, leaving its socket open the way a slow server would.
	await page.getByLabel('Start this piece').fill('Rings');
	await page.getByRole('button', { name: 'Draw', exact: true }).click();
	const first_generation = await first_started;
	first_generation.send({ type: 'node_created', node: generating_node });
	first_generation.send({ type: 'generation_ended', status: 'stopped', message: null });

	// Start a second one, and only then let the first socket close.
	const second_started = mock_generation_socket(page);
	await page.getByRole('textbox').last().fill('Rings again');
	await page.getByRole('button', { name: 'Draw', exact: true }).click();
	const second_generation = await second_started;
	const second_node = { ...generating_node, id: '33333333-3333-4333-8333-333333333334' };
	second_generation.send({ type: 'node_created', node: second_node });
	await first_generation.socket.close();

	// The second generation still hears the page: its step gets a verdict.
	second_generation.send({
		type: 'step_proposed',
		step_token: 'token_1',
		source: sample_diagram_source,
		step_reasoning: 'Reasoning of step 1'
	});
	expect(await second_generation.next_command()).toMatchObject({
		type: 'step_outcome',
		step_token: 'token_1',
		ok: true
	});
	await expect(page.getByRole('button', { name: 'Stop', exact: true })).toBeVisible();
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
	await page.goto(`/projects/${project.id}`);

	const model = page.getByLabel('Model');
	await expect(model).toHaveValue('claude-opus-5-5');
	await expect(model.locator('option')).toHaveText([
		'Claude Opus 5.5',
		'Claude Fable 5.2',
		'GPT-6-Astra'
	]);
	await expect(page.getByText('Can be billed to usage credits.')).toBeHidden();

	// The models are listed under the login each one runs on.
	const headings = await model
		.locator('optgroup')
		.evaluateAll((groups) => groups.map((group) => group.getAttribute('label')));
	expect(headings).toEqual(['Claude plan login', 'ChatGPT plan login']);
	await expect(model.locator('optgroup').last().locator('option')).toHaveText(['GPT-6-Astra']);

	// Choosing the model shows its note and stores its exact id in the project's interface.
	const save_request = page.waitForRequest((request) => request.method() === 'PUT');
	await model.selectOption('claude-fable-5-2');
	await expect(page.getByText('Can be billed to usage credits.')).toBeVisible();
	expect((await save_request).postDataJSON()).toMatchObject({ model: 'claude-fable-5-2' });
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
