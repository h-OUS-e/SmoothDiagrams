/* Helpers for defining prompt controls. */

import type { PromptControl, PromptControlKind } from '#lib/api/api_types.ts';

export const prompt_control_kinds = [
	{ value: 'slider', label: 'Slider' },
	{ value: 'select', label: 'Choice' },
	{ value: 'toggle', label: 'Switch' },
	{ value: 'text', label: 'Text' }
] as const;

// Longest id the server accepts for a prompt control.
const id_length = 40;

// Return an id for a new control: its label in lowercase words, made distinct from the taken ids.
export function build_control_id(label: string, taken_ids: string[]): string {
	const words = label.toLowerCase().replace(/[^a-z0-9]+/g, '_');
	const trimmed = words.replace(/^[^a-z]+/, '').replace(/_+$/, '');
	const base = (trimmed || 'control').slice(0, id_length - 4);

	let id = base;
	for (let suffix = 2; taken_ids.includes(id); suffix += 1) {
		id = `${base}_${suffix}`;
	}
	return id;
}

// Return a new control of one kind, with a starting value and range the director can then change.
export function build_prompt_control(
	label: string,
	kind: PromptControlKind,
	instruction: string,
	taken_ids: string[]
): PromptControl {
	const base = {
		id: build_control_id(label, taken_ids),
		label,
		kind,
		instruction,
		min: null,
		max: null,
		step: null,
		options: null
	};

	switch (kind) {
		case 'slider':
			return { ...base, value: 50, min: 0, max: 100, step: 5 };
		case 'select':
			return { ...base, value: 'first', options: ['first', 'second'] };
		case 'toggle':
			return { ...base, value: false };
		case 'text':
			return { ...base, value: '' };
	}
}

// Return the options a director typed as one line, split at commas.
export function parse_options(text: string): string[] {
	return text
		.split(',')
		.map((option) => option.trim())
		.filter((option) => option !== '');
}
