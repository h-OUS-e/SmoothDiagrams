/* Requests to the local server. */

import { BACKEND_URL } from '$app/env/public';
import type { ParameterValues } from '#lib/features/diagram_viewer/diagram_parameters.ts';
import type {
	ExportDetail,
	ExportInput,
	InterfaceSettings,
	InterfaceSource,
	InterfaceState,
	LibraryItemDetail,
	LibraryOrder,
	ModelCatalog,
	NodeDetail,
	PieceDetail,
	PieceSummary,
	PriorChanges,
	PriorDetail,
	ProjectDetail,
	ProjectSummary,
	TastePriorChanges,
	TastePriorDetail
} from './api_types.ts';

type Fetch = typeof fetch;

// Status of a response that succeeded and has no body.
const no_content_status = 204;

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

// Return a message for the detail of an error response, which is text or a list of problems.
function describe_error_detail(detail: unknown, status: number): string {
	if (typeof detail === 'string') return detail;

	// A refused input lists each problem with a message of its own.
	if (Array.isArray(detail)) {
		const messages = detail.flatMap((problem: unknown) => {
			const message = (problem as { msg?: unknown } | null)?.msg;
			return typeof message === 'string' ? [message.replace(/^Value error, /, '')] : [];
		});
		if (messages.length > 0) return messages.join(' ');
	}
	return `The server answered with status ${status}.`;
}

// Send one request to the local server and return its JSON body, or undefined when it has none.
async function request<Result>(
	fetch_function: Fetch,
	method: string,
	path: string,
	body?: unknown
): Promise<Result> {
	// Send a form as it is, so the browser adds the boundary; send everything else as JSON.
	const is_form = body instanceof FormData;
	const has_json = body !== undefined && !is_form;

	let response: Response;
	try {
		response = await fetch_function(`${BACKEND_URL}${path}`, {
			method,
			headers: has_json ? { 'content-type': 'application/json' } : undefined,
			body: is_form ? body : has_json ? JSON.stringify(body) : undefined
		});
	} catch {
		throw new ServerUnreachableError();
	}

	if (!response.ok) {
		const detail = ((await response.json().catch(() => null)) as { detail?: unknown } | null)
			?.detail;
		throw new ServerResponseError(response.status, describe_error_detail(detail, response.status));
	}
	if (response.status === no_content_status) return undefined as Result;
	return (await response.json()) as Result;
}

// Image types the server accepts as uploads.
export const uploadable_image_types = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];

// Return a form that carries one uploaded file and any text fields that are set.
function build_upload_form(file: File, fields: Record<string, string | null> = {}): FormData {
	const form = new FormData();
	form.append('file', file);
	for (const [name, value] of Object.entries(fields)) {
		if (value !== null) form.append(name, value);
	}
	return form;
}

/* ------------------------------------------------------------------ */
/* Projects and pieces                                                 */
/* ------------------------------------------------------------------ */

export function list_projects(fetch_function: Fetch = fetch): Promise<ProjectSummary[]> {
	return request(fetch_function, 'GET', '/projects');
}

// Create a project, copying an interface version into it when one is named.
export function create_project(
	name: string,
	interface_version_id: string | null
): Promise<ProjectDetail> {
	return request(fetch, 'POST', '/projects', { name, interface_version_id });
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

// Add an image the director edited outside the app as a node, under the step it edits if any.
export function add_uploaded_node(
	piece_id: string,
	file: File,
	parent_step_id: string | null
): Promise<NodeDetail> {
	const form = build_upload_form(file, { parent_step_id });
	return request(fetch, 'POST', `/pieces/${piece_id}/uploaded_nodes`, form);
}

// Ask the taste reason agent why the director may have continued from the node's parent.
export async function offer_taste_reasons(node_id: string): Promise<string[]> {
	const answer = await request<{ candidates: string[] }>(
		fetch,
		'POST',
		`/nodes/${node_id}/taste_reason_candidates`
	);
	return answer.candidates;
}

export function set_taste_reason(
	node_id: string,
	taste_reason: string | null
): Promise<NodeDetail> {
	return request(fetch, 'PATCH', `/nodes/${node_id}/taste_reason`, { taste_reason });
}

// Remember that the director exported a step of a node.
export function add_export(node_id: string, export_input: ExportInput): Promise<ExportDetail> {
	return request(fetch, 'POST', `/nodes/${node_id}/exports`, export_input);
}

/* ------------------------------------------------------------------ */
/* Library, priors, and taste priors                                   */
/* ------------------------------------------------------------------ */

// Return the address an uploaded image is served from.
export function get_asset_url(asset_id: string): string {
	return `${BACKEND_URL}/assets/${asset_id}/file`;
}

// Return every library item in an order; the first similarity order can take a while.
export function list_library(
	order: LibraryOrder,
	fetch_function: Fetch = fetch
): Promise<LibraryItemDetail[]> {
	const query = new URLSearchParams(order);
	return request(fetch_function, 'GET', `/library?${query.toString()}`);
}

export function add_library_image(file: File): Promise<LibraryItemDetail> {
	return request(fetch, 'POST', '/library/images', build_upload_form(file));
}

export function add_library_node(node_id: string): Promise<LibraryItemDetail> {
	return request(fetch, 'POST', '/library/nodes', { node_id });
}

export function remove_library_item(item_id: string): Promise<void> {
	return request(fetch, 'DELETE', `/library/${item_id}`);
}

export function list_priors(
	project_id: string,
	fetch_function: Fetch = fetch
): Promise<PriorDetail[]> {
	return request(fetch_function, 'GET', `/projects/${project_id}/priors`);
}

export function add_library_prior(
	project_id: string,
	library_item_id: string
): Promise<PriorDetail> {
	return request(fetch, 'POST', `/projects/${project_id}/priors`, { library_item_id });
}

export function add_text_prior(
	project_id: string,
	name: string,
	text_content: string
): Promise<PriorDetail> {
	return request(fetch, 'POST', `/projects/${project_id}/priors`, { name, text_content });
}

export function change_prior(prior_id: string, changes: PriorChanges): Promise<PriorDetail> {
	return request(fetch, 'PATCH', `/priors/${prior_id}`, changes);
}

export function remove_prior(prior_id: string): Promise<void> {
	return request(fetch, 'DELETE', `/priors/${prior_id}`);
}

export function list_taste_priors(fetch_function: Fetch = fetch): Promise<TastePriorDetail[]> {
	return request(fetch_function, 'GET', '/taste_priors');
}

export function add_text_taste_prior(
	kind: 'text' | 'skill',
	name: string,
	text_content: string
): Promise<TastePriorDetail> {
	return request(fetch, 'POST', '/taste_priors', { kind, name, text_content });
}

export function add_image_taste_prior(file: File): Promise<TastePriorDetail> {
	return request(fetch, 'POST', '/taste_priors/images', build_upload_form(file));
}

export function change_taste_prior(
	taste_prior_id: string,
	changes: TastePriorChanges
): Promise<TastePriorDetail> {
	return request(fetch, 'PATCH', `/taste_priors/${taste_prior_id}`, changes);
}

export function remove_taste_prior(taste_prior_id: string): Promise<void> {
	return request(fetch, 'DELETE', `/taste_priors/${taste_prior_id}`);
}

/* ------------------------------------------------------------------ */
/* Interface versions                                                  */
/* ------------------------------------------------------------------ */

export function get_interface(
	project_id: string,
	fetch_function: Fetch = fetch
): Promise<InterfaceState> {
	return request(fetch_function, 'GET', `/projects/${project_id}/interface`);
}

// Store new settings; the server keeps a version that produced work and continues in a new one.
export function save_interface(
	project_id: string,
	settings: InterfaceSettings
): Promise<InterfaceState> {
	return request(fetch, 'PUT', `/projects/${project_id}/interface`, settings);
}

export function restore_interface(
	project_id: string,
	interface_version_id: string
): Promise<InterfaceState> {
	return request(fetch, 'POST', `/projects/${project_id}/interface/restore`, {
		interface_version_id
	});
}

// Return every interface version a new project could start from.
export function list_interface_sources(fetch_function: Fetch = fetch): Promise<InterfaceSource[]> {
	return request(fetch_function, 'GET', '/interface_versions');
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
