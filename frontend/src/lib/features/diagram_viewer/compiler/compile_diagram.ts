/* Compile one diagram source into code the sandbox can run. */

import { compile, parse } from 'svelte/compiler';
import type { DiagramAnimation, DiagramParameter } from '../diagram_parameters.ts';
import { read_diagram_exports } from './read_diagram_exports.ts';

export type CompileOutcome =
	| { ok: true; code: string; parameters: DiagramParameter[]; animation: DiagramAnimation | null }
	| { ok: false; message: string };

const diagram_filename = 'Diagram.svelte';

// Return a message for a thrown compile error, with the offending lines when known.
function describe_compile_error(error: unknown): string {
	if (!(error instanceof Error)) return String(error);

	const diagnostic = error as Error & { frame?: string; start?: { line: number } };
	if (diagnostic.frame && diagnostic.start) {
		return `${diagnostic.message} (line ${diagnostic.start.line})\n${diagnostic.frame}`;
	}
	return error.message;
}

// Return compiled code and exposed controls for a diagram source, or why it cannot compile.
export function compile_diagram(source: string): CompileOutcome {
	try {
		// Read what the source exposes first, so broken source rules are reported together.
		const root = parse(source, { modern: true, filename: diagram_filename });
		const diagram_exports = read_diagram_exports(root);
		if (diagram_exports.problems.length > 0) {
			return { ok: false, message: diagram_exports.problems.join('\n') };
		}

		const result = compile(source, {
			filename: diagram_filename,
			generate: 'client',
			runes: true,
			css: 'injected',
			dev: false,
			discloseVersion: false
		});
		return {
			ok: true,
			code: result.js.code,
			parameters: diagram_exports.parameters,
			animation: diagram_exports.animation
		};
	} catch (error) {
		return { ok: false, message: describe_compile_error(error) };
	}
}
