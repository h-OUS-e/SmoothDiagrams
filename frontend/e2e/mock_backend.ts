/* Stand in for the local server in browser tests, so they need neither Python nor a model. */

import type { Page, WebSocketRoute } from '@playwright/test';
import type {
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
		{ id: 'claude-opus-5-5', label: 'Claude Opus 5.5', note: null },
		{ id: 'claude-fable-5-2', label: 'Claude Fable 5.2', note: 'Can be billed to usage credits.' }
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
	created_at,
	parameter_values: {},
	steps: [],
	parent_step: null
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

// Answer the requests a project page makes with one project that has one empty piece.
export async function mock_project_routes(page: Page) {
	await page.route(`${backend_url}/projects`, (route) =>
		route.fulfill({ json: route.request().method() === 'POST' ? project : [project_summary] })
	);
	await page.route(`${backend_url}/projects/${project.id}`, (route) =>
		route.fulfill({ json: project })
	);
	await page.route(`${backend_url}/models`, (route) => route.fulfill({ json: model_catalog }));
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
