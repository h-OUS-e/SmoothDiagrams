/* Promise-based access to the compile worker, shared by everything on the page that needs it. */

import type { ParameterValues } from '../diagram_parameters.ts';
import type { CompileOutcome } from './compile_diagram.ts';
import type { WorkerOutcome, WorkerRequest, WorkerResponse, WorkerTask } from './compile_worker.ts';
import type { ReplaceDefaultsOutcome } from './replace_prop_defaults.ts';

let worker: Worker | null = null;
let last_request_id = 0;
const pending_requests = new Map<number, (result: WorkerOutcome) => void>();

// Return the shared worker, starting it on first use.
function get_worker(): Worker {
	if (worker) return worker;

	worker = new Worker(new URL('./compile_worker.ts', import.meta.url), { type: 'module' });
	worker.addEventListener('message', (event: MessageEvent<WorkerResponse>) => {
		const resolve = pending_requests.get(event.data.request_id);
		pending_requests.delete(event.data.request_id);
		resolve?.(event.data.result);
	});
	return worker;
}

// Run one task in the worker and return its outcome. Call only in the browser.
function run_in_worker(task: WorkerTask): Promise<WorkerOutcome> {
	last_request_id += 1;
	const request: WorkerRequest = { request_id: last_request_id, task };

	return new Promise((resolve) => {
		pending_requests.set(request.request_id, resolve);
		get_worker().postMessage(request);
	});
}

// Return the error for a worker that answered a task with the outcome of another kind.
function build_mismatch_error(task_kind: WorkerTask['kind']): Error {
	return new Error(`The compile worker did not answer the ${task_kind} task it was given.`);
}

// Compile a diagram source in the worker.
export async function compile_in_worker(source: string): Promise<CompileOutcome> {
	const result = await run_in_worker({ kind: 'compile', source });
	if (result.kind !== 'compile') throw build_mismatch_error('compile');
	return result.outcome;
}

// Write parameter values into a diagram source as the defaults of its props, in the worker.
export async function replace_prop_defaults_in_worker(
	source: string,
	values: ParameterValues
): Promise<ReplaceDefaultsOutcome> {
	const result = await run_in_worker({ kind: 'replace_prop_defaults', source, values });
	if (result.kind !== 'replace_prop_defaults') throw build_mismatch_error('replace_prop_defaults');
	return result.outcome;
}
