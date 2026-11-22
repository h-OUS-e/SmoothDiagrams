/* Requests to the local server. */

import { BACKEND_URL } from '$app/env/public';
import type { ParameterValues } from '#lib/features/diagram_viewer/diagram_parameters.ts';
import type {
	ModelCatalog,
	NodeDetail,
	PieceDetail,
	PieceSummary,
	ProjectDetail,
	ProjectSummary
} from './api_types.ts';

type Fetch = typeof fetch;

// Thrown when the local server cannot be reached at all.
export class ServerUnreachableError extends Error {
	constructor() {
		super('The local server is not running.');
	}
}

// Thrown when the local server answers with an error status.
export class ServerResponseError extends Error {
	status: number;

	constructor(status: number, message: string) {
		super(message);
		this.status = status;
	}
}

// Send one request to the local server and return its JSON body.
async function request<Result>(
	fetch_function: Fetch,
	method: string,
	path: string,
	body?: unknown
): Promise<Result> {
	let response: Response;
	try {
		response = await fetch_function(`${BACKEND_URL}${path}`, {
			method,
			headers: body === undefined ? undefined : { 'content-type': 'application/json' },
			body: body === undefined ? undefined : JSON.stringify(body)
		});
	} catch {
		throw new ServerUnreachableError();
	}

	if (!response.ok) {
		const detail = ((await response.json().catch(() => null)) as { detail?: unknown } | null)
			?.detail;
		throw new ServerResponseError(
			response.status,
			typeof detail === 'string' ? detail : `The server answered with status ${response.status}.`
		);
	}
	return (await response.json()) as Result;
}

/* ------------------------------------------------------------------ */
/* Projects and pieces                                                 */
/* ------------------------------------------------------------------ */

export function list_projects(fetch_function: Fetch = fetch): Promise<ProjectSummary[]> {
	return request(fetch_function, 'GET', '/projects');
}

export function create_project(name: string): Promise<ProjectDetail> {
	return request(fetch, 'POST', '/projects', { name });
}

export function get_project(
	project_id: string,
	fetch_function: Fetch = fetch
): Promise<ProjectDetail> {
	return request(fetch_function, 'GET', `/projects/${project_id}`);
}

export function rename_project(project_id: string, name: string): Promise<ProjectDetail> {
	return request(fetch, 'PATCH', `/projects/${project_id}`, { name });
}

export function create_piece(project_id: string, name: string): Promise<PieceSummary> {
	return request(fetch, 'POST', `/projects/${project_id}/pieces`, { name });
}

export function get_piece(piece_id: string, fetch_function: Fetch = fetch): Promise<PieceDetail> {
	return request(fetch_function, 'GET', `/pieces/${piece_id}`);
}

/* ------------------------------------------------------------------ */
/* Nodes                                                               */
/* ------------------------------------------------------------------ */

export function get_node(node_id: string, fetch_function: Fetch = fetch): Promise<NodeDetail> {
	return request(fetch_function, 'GET', `/nodes/${node_id}`);
}

export function set_parameter_values(
	node_id: string,
	parameter_values: ParameterValues
): Promise<NodeDetail> {
	return request(fetch, 'PATCH', `/nodes/${node_id}/parameter_values`, { parameter_values });
}

/* ------------------------------------------------------------------ */
/* Generations                                                         */
/* ------------------------------------------------------------------ */

export function get_model_catalog(fetch_function: Fetch = fetch): Promise<ModelCatalog> {
	return request(fetch_function, 'GET', '/models');
}

// Return the WebSocket address of the route that runs generations.
export function get_generations_url(): string {
	return `${BACKEND_URL.replace(/^http/, 'ws')}/generations`;
}
