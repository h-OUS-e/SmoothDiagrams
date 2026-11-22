/* Read a diagram's exposed parameters and animation from its parsed source, without running it. */

import type * as ESTree from 'estree';
import type { AST } from 'svelte/compiler';
import {
	parameter_groups,
	time_prop,
	type DiagramAnimation,
	type DiagramParameter,
	type ParameterGroup
} from '../diagram_parameters.ts';
import { diagram_modules } from '../sandbox/sandbox_modules.ts';

export type DiagramExports = {
	parameters: DiagramParameter[];
	animation: DiagramAnimation | null;
	problems: string[];
};

type RawRecord = Record<string, unknown>;

// Default expressions by prop name; null marks a prop with no default.
export type PropDefaults = Map<string, ESTree.Node | null>;

class NotLiteralError extends Error {}

const identifier_pattern = /^[A-Za-z_$][A-Za-z0-9_$]*$/;
const color_pattern = /^#[0-9a-fA-F]{6}$/;

/* ------------------------------------------------------------------ */
/* Literal evaluation                                                  */
/* ------------------------------------------------------------------ */

// Return the plain value a literal expression stands for, or throw NotLiteralError.
function evaluate_literal(node: ESTree.Node): unknown {
	// Unwrap TypeScript assertions, which the estree types do not describe.
	const node_type: string = node.type;
	if (node_type === 'TSAsExpression' || node_type === 'TSSatisfiesExpression') {
		return evaluate_literal((node as unknown as { expression: ESTree.Node }).expression);
	}

	switch (node.type) {
		case 'Literal': {
			const value = node.value;
			if (value === null || ['string', 'number', 'boolean'].includes(typeof value)) return value;
			throw new NotLiteralError();
		}
		case 'TemplateLiteral': {
			if (node.expressions.length > 0) throw new NotLiteralError();
			return node.quasis[0].value.cooked ?? '';
		}
		case 'UnaryExpression': {
			const value = evaluate_literal(node.argument);
			if (typeof value !== 'number') throw new NotLiteralError();
			if (node.operator === '-') return -value;
			if (node.operator === '+') return value;
			throw new NotLiteralError();
		}
		case 'ArrayExpression': {
			return node.elements.map((element) => {
				if (!element || element.type === 'SpreadElement') throw new NotLiteralError();
				return evaluate_literal(element);
			});
		}
		case 'ObjectExpression': {
			const record: RawRecord = {};
			for (const property of node.properties) {
				if (property.type !== 'Property' || property.computed || property.kind !== 'init') {
					throw new NotLiteralError();
				}
				record[read_property_key(property.key)] = evaluate_literal(property.value);
			}
			return record;
		}
		default:
			throw new NotLiteralError();
	}
}

// Return the name of a plain object key, or throw NotLiteralError.
function read_property_key(key: ESTree.Node): string {
	if (key.type === 'Identifier') return key.name;
	if (key.type === 'Literal' && typeof key.value === 'string') return key.value;
	throw new NotLiteralError();
}

/* ------------------------------------------------------------------ */
/* Source lookups                                                      */
/* ------------------------------------------------------------------ */

// Return the expression assigned to an exported const in the module script, if any.
function find_module_export(module: AST.Script | null, name: string): ESTree.Node | null {
	for (const statement of module?.content.body ?? []) {
		if (statement.type !== 'ExportNamedDeclaration') continue;
		if (statement.declaration?.type !== 'VariableDeclaration') continue;

		for (const declarator of statement.declaration.declarations) {
			if (declarator.id.type === 'Identifier' && declarator.id.name === name) {
				return declarator.init ?? null;
			}
		}
	}
	return null;
}

// Return the default of every prop destructured from $props() in the instance script.
export function read_prop_defaults(instance: AST.Script | null): PropDefaults {
	const defaults: PropDefaults = new Map();

	for (const statement of instance?.content.body ?? []) {
		if (statement.type !== 'VariableDeclaration') continue;

		for (const declarator of statement.declarations) {
			// Keep only the declaration that destructures the $props() call.
			const init = declarator.init;
			const calls_props =
				init?.type === 'CallExpression' &&
				init.callee.type === 'Identifier' &&
				init.callee.name === '$props';
			if (!calls_props || declarator.id.type !== 'ObjectPattern') continue;

			for (const property of declarator.id.properties) {
				if (property.type !== 'Property' || property.key.type !== 'Identifier') continue;
				const has_default = property.value.type === 'AssignmentPattern';
				defaults.set(
					property.key.name,
					has_default ? (property.value as ESTree.AssignmentPattern).right : null
				);
			}
		}
	}
	return defaults;
}

// Return a problem for every import that the sandbox does not provide.
function find_import_problems(root: AST.Root): string[] {
	const allowed_specifiers = diagram_modules.map((module) => module.specifier);
	const problems: string[] = [];

	for (const script of [root.module, root.instance]) {
		for (const statement of script?.content.body ?? []) {
			if (statement.type !== 'ImportDeclaration') continue;
			const specifier = String(statement.source.value);
			if (!allowed_specifiers.includes(specifier)) {
				problems.push(
					`Import "${specifier}" is not available. A diagram may only import from: ${allowed_specifiers.join(', ')}.`
				);
			}
		}
	}
	return problems;
}

/* ------------------------------------------------------------------ */
/* Parameters                                                          */
/* ------------------------------------------------------------------ */

// Return whether a value is a plain object.
function is_record(value: unknown): value is RawRecord {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

// Return whether a value is a finite number.
function is_finite_number(value: unknown): value is number {
	return typeof value === 'number' && Number.isFinite(value);
}

// Return the literal default of a parameter's prop, or add a problem and return undefined.
function read_default(name: string, prop_defaults: PropDefaults, problems: string[]): unknown {
	if (!prop_defaults.has(name)) {
		problems.push(`Parameter "${name}" is not destructured from $props().`);
		return undefined;
	}

	const default_node = prop_defaults.get(name);
	if (!default_node) {
		problems.push(`Parameter "${name}" needs a default value in the $props() destructuring.`);
		return undefined;
	}

	try {
		return evaluate_literal(default_node);
	} catch {
		problems.push(`The default of parameter "${name}" in $props() must be a literal value.`);
		return undefined;
	}
}

/**
 * Build one exposed parameter from its entry in `parameters` and its default in $props().
 *
 * Args:
 *   entry: One evaluated item of the exported `parameters` array.
 *   prop_defaults: Defaults of the props destructured from $props().
 *   problems: List that receives a message for everything wrong with the entry.
 *
 * Returns:
 *   The parameter, or null when the entry has a problem.
 */
function read_parameter(
	entry: unknown,
	prop_defaults: PropDefaults,
	problems: string[]
): DiagramParameter | null {
	const problem_count = problems.length;

	// Check the fields every parameter shares.
	if (!is_record(entry)) {
		problems.push('Every item of `parameters` must be an object.');
		return null;
	}
	const { name, label, group, kind } = entry;
	if (typeof name !== 'string' || !identifier_pattern.test(name)) {
		problems.push(`Parameter name ${JSON.stringify(name)} must be a valid identifier.`);
		return null;
	}
	if (name === time_prop) {
		problems.push(`"${time_prop}" is driven by the viewer and cannot be an exposed parameter.`);
		return null;
	}
	if (typeof label !== 'string' || label.trim() === '') {
		problems.push(`Parameter "${name}" needs a non-empty label.`);
	}
	if (!parameter_groups.includes(group as ParameterGroup)) {
		problems.push(`Parameter "${name}" needs a group: one of ${parameter_groups.join(', ')}.`);
	}
	if ('value' in entry) {
		problems.push(
			`Parameter "${name}" must not set "value"; its default comes from the $props() destructuring.`
		);
	}

	// Check the default against the rules of the parameter's kind.
	const value = read_default(name, prop_defaults, problems);
	const base = { name, label: label as string, group: group as ParameterGroup };
	let parameter: DiagramParameter | null = null;

	switch (kind) {
		case 'number': {
			const { min, max, step } = entry;
			if (!is_finite_number(min) || !is_finite_number(max) || !is_finite_number(step)) {
				problems.push(`Number parameter "${name}" needs numeric min, max, and step.`);
			} else if (min >= max || step <= 0) {
				problems.push(`Number parameter "${name}" needs min below max and a positive step.`);
			} else if (!is_finite_number(value) || value < min || value > max) {
				problems.push(
					`The default of number parameter "${name}" must be a number from min to max.`
				);
			} else {
				parameter = { ...base, kind, value, min, max, step };
			}
			break;
		}
		case 'color': {
			if (typeof value !== 'string' || !color_pattern.test(value)) {
				problems.push(`The default of color parameter "${name}" must look like "#1a2b3c".`);
			} else {
				parameter = { ...base, kind, value };
			}
			break;
		}
		case 'text': {
			if (typeof value !== 'string') {
				problems.push(`The default of text parameter "${name}" must be a string.`);
			} else {
				parameter = { ...base, kind, value };
			}
			break;
		}
		case 'boolean': {
			if (typeof value !== 'boolean') {
				problems.push(`The default of boolean parameter "${name}" must be true or false.`);
			} else {
				parameter = { ...base, kind, value };
			}
			break;
		}
		case 'select': {
			const options = entry.options;
			const options_are_valid =
				Array.isArray(options) &&
				options.length > 0 &&
				options.every((option) => typeof option === 'string');
			if (!options_are_valid) {
				problems.push(`Select parameter "${name}" needs a non-empty array of string options.`);
			} else if (typeof value !== 'string' || !options.includes(value)) {
				problems.push(`The default of select parameter "${name}" must be one of its options.`);
			} else {
				parameter = { ...base, kind, value, options: options };
			}
			break;
		}
		default:
			problems.push(
				`Parameter "${name}" needs a kind: one of number, color, text, boolean, select.`
			);
	}

	return problems.length === problem_count ? parameter : null;
}

// Return every exposed parameter declared by the module script's `parameters` export.
function read_parameters(root: AST.Root, problems: string[]): DiagramParameter[] {
	const parameters_node = find_module_export(root.module, 'parameters');
	if (!parameters_node) return [];

	// Evaluate the export, which must be plain literal data.
	let entries: unknown;
	try {
		entries = evaluate_literal(parameters_node);
	} catch {
		problems.push('`parameters` must be an array of object literals with literal values only.');
		return [];
	}
	if (!Array.isArray(entries)) {
		problems.push('`parameters` must be an array.');
		return [];
	}

	// Build each parameter, rejecting names that repeat.
	const prop_defaults = read_prop_defaults(root.instance);
	const parameters: DiagramParameter[] = [];
	for (const entry of entries) {
		const parameter = read_parameter(entry, prop_defaults, problems);
		if (!parameter) continue;
		if (parameters.some((existing) => existing.name === parameter.name)) {
			problems.push(`Parameter "${parameter.name}" is declared more than once.`);
			continue;
		}
		parameters.push(parameter);
	}
	return parameters;
}

/* ------------------------------------------------------------------ */
/* Animation                                                           */
/* ------------------------------------------------------------------ */

// Return the animation declared by the module script's `animation` export, if any.
function read_animation(root: AST.Root, problems: string[]): DiagramAnimation | null {
	const animation_node = find_module_export(root.module, 'animation');
	if (!animation_node) return null;

	let animation: unknown;
	try {
		animation = evaluate_literal(animation_node);
	} catch {
		problems.push('`animation` must be an object literal with literal values only.');
		return null;
	}

	if (!is_record(animation) || !is_finite_number(animation.duration) || animation.duration <= 0) {
		problems.push('`animation` needs a positive duration in seconds.');
		return null;
	}
	if (animation.loop !== undefined && typeof animation.loop !== 'boolean') {
		problems.push('`animation.loop` must be true or false.');
		return null;
	}
	return { duration: animation.duration, loop: animation.loop ?? false };
}

/* ------------------------------------------------------------------ */
/* Entry point                                                         */
/* ------------------------------------------------------------------ */

// Return what a parsed diagram exposes, plus a message for every broken source rule.
export function read_diagram_exports(root: AST.Root): DiagramExports {
	const problems = find_import_problems(root);
	const parameters = read_parameters(root, problems);
	const animation = read_animation(root, problems);
	return { parameters, animation, problems };
}
