/* Stand in for the local server in browser tests, so they need neither Python nor a model. */

import type { Page, WebSocketRoute } from '@playwright/test';
import type {
	InterfaceState,
	ModelCatalog,
	NodeDetail,
	PieceDetail,
	ProjectDetail,
	ProjectSummary,
	StepDetail
} from '../src/lib/api/api_types.ts';
import type { SteeringCommand, StartCommand } from '../src/lib/api/generation_socket.ts';

export const backend_url = 'http://localhost:8000';

const created_at = '2026-11-21T10:00:00Z';

export const project: ProjectDetail = {
	id: '11111111-1111-4111-8111-111111111111',
	name: 'November postcards',
	created_at,
	pieces: [
		{
			id: '22222222-2222-4222-8222-222222222222',
			project_id: '11111111-1111-4111-8111-111111111111',
			name: 'Piece 1',
			created_at
		}
	]
};

export const model_catalog: ModelCatalog = {
	default_model: 'claude-opus-5-5',
	models: [
		{ id: 'claude-opus-5-5', label: 'Claude Opus 5.5', vendor: 'anthropic', note: null },
		{
			id: 'claude-fable-5-2',
			label: 'Claude Fable 5.2',
			vendor: 'anthropic',
			note: 'Can be billed to usage credits.'
		},
		{ id: 'gpt-6-astra', label: 'GPT-6-Astra', vendor: 'openai', note: null }
	]
};

// The interface a project starts with, trimmed to one prompt control of each common kind.
export const interface_state: InterfaceState = {
	current_version_id: '99999999-9999-4999-8999-999999999991',
	version_number: 1,
	settings: {
		model: 'claude-opus-5-5',
		is_step_by_step: true,
		offers_taste_reasons: true,
		prompt_templates: {
			direction: '',
			step_by_step: 'Build the diagram in steps.',
			single_pass: 'Write the diagram in one pass.'
		},
		prompt_controls: [
			{
				id: 'ratio',
				label: 'Ratio',
				kind: 'select',
				instruction: 'Use a ratio of {value}.',
				value: '4:3',
				min: null,
				max: null,
				step: null,
				options: ['4:3', '1:1']
			},
			{
				id: 'novelty',
				label: 'Novelty',
				kind: 'slider',
				instruction: 'Novelty is {value} out of 100.',
				value: 30,
				min: 0,
				max: 100,
				step: 5,
				options: null
			}
		],
		disabled_taste_prior_ids: []
	},
	versions: [
		{
			id: '99999999-9999-4999-8999-999999999991',
			version_number: 1,
			created_at,
			node_count: 0,
			is_current: true
		}
	]
};

export const project_summary: ProjectSummary = {
	id: project.id,
	name: project.name,
	created_at,
	piece_count: 1,
	cover_svg: null
};

export const empty_piece: PieceDetail = { ...project.pieces[0], nodes: [] };

export const generating_node: NodeDetail = {
	id: '33333333-3333-4333-8333-333333333333',
	piece_id: empty_piece.id,
	parent_node_id: null,
	parent_step_id: null,
	kind: 'generated',
	status: 'generating',
	prompt: 'Rings',
	model: 'claude-opus-5-5',
	is_step_by_step: true,
	failure_message: null,
	image_asset_id: null,
	interface_version_id: null,
	taste_reason_candidates: null,
	taste_reason: null,
	created_at,
	parameter_values: {},
	steps: [],
	parent_step: null,
	exports: []
};

// Return a saved step of the generating node.
export function build_step(step_index: number, source: string, render_svg: string): StepDetail {
	return {
		id: `44444444-4444-4444-8444-00000000000${step_index}`,
		node_id: generating_node.id,
		step_index,
		source,
		step_reasoning: `Reasoning of step ${step_index + 1}`,
		render_svg,
		is_rejected: false,
		rejection_reason: null,
		created_at
	};
}

// Markup a finished step of the sample diagram is stored with.
export const sample_render_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"/>';

// Return a node that finished with one step, changed where a test needs it different.
export function build_finished_node(source: string, changes: Partial<NodeDetail> = {}): NodeDetail {
	return {
		...generating_node,
		status: 'finished',
		steps: [build_step(0, source, sample_render_svg)],
		...changes
	};
}

// Answer the piece and node requests with a piece whose only node is the given one.
export async function mock_piece_with_node(page: Page, node: NodeDetail) {
	const piece: PieceDetail = {
		...empty_piece,
		nodes: [
			{
				...node,
				step_count: node.steps.length,
				render_svg: node.steps.at(-1)?.render_svg ?? null,
				export_count: node.exports.length
			}
		]
	};
	await page.route(`${backend_url}/pieces/${piece.id}`, (route) => route.fulfill({ json: piece }));
	await page.route(`${backend_url}/nodes/${node.id}`, (route) => route.fulfill({ json: node }));
}

// Answer the requests a project page makes with one project that has one empty piece.
export async function mock_project_routes(page: Page) {
	await page.route(`${backend_url}/projects`, (route) =>
		route.fulfill({ json: route.request().method() === 'POST' ? project : [project_summary] })
	);
	await page.route(`${backend_url}/projects/${project.id}`, (route) =>
		route.fulfill({ json: project })
	);
	await page.route(`${backend_url}/models`, (route) => route.fulfill({ json: model_catalog }));
	await page.route(`${backend_url}/interface_versions`, (route) => route.fulfill({ json: [] }));

	// Answer a saved interface with what was sent, the way the server does for an unused version.
	await page.route(`${backend_url}/projects/${project.id}/interface`, (route) => {
		const request = route.request();
		const settings =
			request.method() === 'PUT'
				? (request.postDataJSON() as InterfaceState['settings'])
				: interface_state.settings;
		return route.fulfill({ json: { ...interface_state, settings } });
	});
	await page.route(`${backend_url}/library?*`, (route) => route.fulfill({ json: [] }));
	await page.route(`${backend_url}/projects/${project.id}/priors`, (route) =>
		route.fulfill({ json: [] })
	);
	await page.route(`${backend_url}/taste_priors`, (route) => route.fulfill({ json: [] }));
	await page.route(`${backend_url}/pieces/${empty_piece.id}`, (route) =>
		route.fulfill({ json: empty_piece })
	);
	await page.route(`${backend_url}/nodes/${generating_node.id}/parameter_values`, (route) =>
		route.fulfill({ json: generating_node })
	);
}

export type MockGeneration = {
	socket: WebSocketRoute;
	start: StartCommand;
	// Resolve with the next command the page sends.
	next_command: () => Promise<SteeringCommand>;
	// Send one event to the page.
	send: (event: object) => void;
};

// Take over the generation socket and resolve once the page has sent its start command.
export function mock_generation_socket(page: Page): Promise<MockGeneration> {
	return new Promise((resolve) => {
		void page.routeWebSocket(`${backend_url.replace('http', 'ws')}/generations`, (socket) => {
			const commands: SteeringCommand[] = [];
			const waiting: ((command: SteeringCommand) => void)[] = [];
			let has_started = false;

			socket.onMessage((message) => {
				const data = JSON.parse(String(message)) as StartCommand | SteeringCommand;

				// Hand over control with the first message, which is the start command.
				if (!has_started && data.type === 'start') {
					has_started = true;
					resolve({
						socket,
						start: data,
						next_command: () =>
							new Promise((resolve_command) => {
								const queued = commands.shift();
								if (queued) resolve_command(queued);
								else waiting.push(resolve_command);
							}),
						send: (event) => socket.send(JSON.stringify(event))
					});
					return;
				}

				// Queue every later command until the test asks for it.
				const command = data as SteeringCommand;
				const resolve_command = waiting.shift();
				if (resolve_command) resolve_command(command);
				else commands.push(command);
			});
		});
	});
}
