/* Web worker that compiles diagram sources off the main thread. */

import { compile_diagram, type CompileOutcome } from './compile_diagram.ts';

export type CompileRequest = {
	request_id: number;
	source: string;
};

export type CompileResponse = {
	request_id: number;
	outcome: CompileOutcome;
};

self.addEventListener('message', (event: MessageEvent<CompileRequest>) => {
	const { request_id, source } = event.data;
	const response: CompileResponse = { request_id, outcome: compile_diagram(source) };
	self.postMessage(response);
});
