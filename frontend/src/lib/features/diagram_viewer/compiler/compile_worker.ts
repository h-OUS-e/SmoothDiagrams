/* Web worker that does everything needing the Svelte compiler, off the main thread. */

import type { ParameterValues } from '../diagram_parameters.ts';
import { compile_diagram, type CompileOutcome } from './compile_diagram.ts';
import { replace_prop_defaults, type ReplaceDefaultsOutcome } from './replace_prop_defaults.ts';

export type WorkerTask =
	| { kind: 'compile'; source: string }
	| { kind: 'replace_prop_defaults'; source: string; values: ParameterValues };

export type WorkerOutcome =
	| { kind: 'compile'; outcome: CompileOutcome }
	| { kind: 'replace_prop_defaults'; outcome: ReplaceDefaultsOutcome };

export type WorkerRequest = {
	request_id: number;
	task: WorkerTask;
};

export type WorkerResponse = {
	request_id: number;
	result: WorkerOutcome;
};

// Do one task and return its outcome under the same kind.
function run_task(task: WorkerTask): WorkerOutcome {
	switch (task.kind) {
		case 'compile':
			return { kind: 'compile', outcome: compile_diagram(task.source) };
		case 'replace_prop_defaults':
			return {
				kind: 'replace_prop_defaults',
				outcome: replace_prop_defaults(task.source, task.values)
			};
	}
}

self.addEventListener('message', (event: MessageEvent<WorkerRequest>) => {
	const { request_id, task } = event.data;
	const response: WorkerResponse = { request_id, result: run_task(task) };
	self.postMessage(response);
});
