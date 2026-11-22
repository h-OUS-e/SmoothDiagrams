/* Promise-based access to the compile worker, shared by every viewer on the page. */

import type { CompileOutcome } from './compile_diagram.ts';
import type { CompileRequest, CompileResponse } from './compile_worker.ts';

let worker: Worker | null = null;
let last_request_id = 0;
const pending_requests = new Map<number, (outcome: CompileOutcome) => void>();

// Return the shared worker, starting it on first use.
function get_worker(): Worker {
	if (worker) return worker;

	worker = new Worker(new URL('./compile_worker.ts', import.meta.url), { type: 'module' });
	worker.addEventListener('message', (event: MessageEvent<CompileResponse>) => {
		const resolve = pending_requests.get(event.data.request_id);
		pending_requests.delete(event.data.request_id);
		resolve?.(event.data.outcome);
	});
	return worker;
}

// Compile a diagram source in the worker. Call only in the browser.
export function compile_in_worker(source: string): Promise<CompileOutcome> {
	last_request_id += 1;
	const request: CompileRequest = { request_id: last_request_id, source };

	return new Promise((resolve) => {
		pending_requests.set(request.request_id, resolve);
		get_worker().postMessage(request);
	});
}
