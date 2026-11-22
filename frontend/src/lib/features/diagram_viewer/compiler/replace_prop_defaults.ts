/* Write chosen parameter values into a diagram source as the defaults of its props. */

import { parse } from 'svelte/compiler';
import type { ParameterValue, ParameterValues } from '../diagram_parameters.ts';
import { diagram_filename } from './compile_diagram.ts';
import { read_prop_defaults } from './read_diagram_exports.ts';

export type ReplaceDefaultsOutcome = { ok: true; source: string } | { ok: false; message: string };

// Where a parsed expression sits in the source, which the parser records on every node.
type SourceRange = {
	start: number;
	end: number;
};

type Replacement = SourceRange & {
	text: string;
};

// Return a value as the literal a script would spell it with.
function write_literal(value: ParameterValue): string {
	if (typeof value !== 'string') return String(value);

	// Turn the double-quoted spelling into a single-quoted one, keeping every other escape.
	const escaped = JSON.stringify(value)
		.slice(1, -1)
		.replace(/\\(.)/gs, (escape: string, character: string) => (character === '"' ? '"' : escape))
		.replaceAll("'", "\\'");

	// Spell "<" as an escape, so a value can never close the script element it is written into.
	return `'${escaped.replaceAll('<', '\\u003c')}'`;
}

/**
 * Return a diagram source whose props default to the given values.
 *
 * A value replaces the default only where a prop of that name has one, so the source keeps
 * rendering what the viewer shows with those values, without being handed any.
 *
 * Args:
 *   source: Source of a diagram that compiles.
 *   values: Parameter values by prop name.
 *
 * Returns:
 *   The changed source, or why the source could not be read.
 */
export function replace_prop_defaults(
	source: string,
	values: ParameterValues
): ReplaceDefaultsOutcome {
	// Find where each default is written.
	let prop_defaults;
	try {
		const root = parse(source, { modern: true, filename: diagram_filename });
		prop_defaults = read_prop_defaults(root.instance);
	} catch (error) {
		return { ok: false, message: error instanceof Error ? error.message : String(error) };
	}

	const replacements: Replacement[] = [];
	for (const [name, value] of Object.entries(values)) {
		const default_node = prop_defaults.get(name) as SourceRange | null | undefined;
		if (!default_node) continue;
		replacements.push({
			start: default_node.start,
			end: default_node.end,
			text: write_literal(value)
		});
	}

	// Replace from the end of the source backwards, so the earlier positions stay right.
	let changed_source = source;
	for (const replacement of replacements.sort((first, second) => second.start - first.start)) {
		changed_source =
			changed_source.slice(0, replacement.start) +
			replacement.text +
			changed_source.slice(replacement.end);
	}
	return { ok: true, source: changed_source };
}
