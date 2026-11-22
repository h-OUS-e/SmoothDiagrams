/* Types describing what a diagram's source exposes to the Controls. */

export const parameter_groups = ['general', 'styling', 'animation', 'copy'] as const;

export type ParameterGroup = (typeof parameter_groups)[number];

type ParameterBase = {
	name: string;
	label: string;
	group: ParameterGroup;
};

export type NumberParameter = ParameterBase & {
	kind: 'number';
	value: number;
	min: number;
	max: number;
	step: number;
};

export type ColorParameter = ParameterBase & {
	kind: 'color';
	value: string;
};

export type TextParameter = ParameterBase & {
	kind: 'text';
	value: string;
};

export type BooleanParameter = ParameterBase & {
	kind: 'boolean';
	value: boolean;
};

export type SelectParameter = ParameterBase & {
	kind: 'select';
	value: string;
	options: string[];
};

export type DiagramParameter =
	NumberParameter | ColorParameter | TextParameter | BooleanParameter | SelectParameter;

export type ParameterValue = DiagramParameter['value'];

export type ParameterValues = Record<string, ParameterValue>;

export type DiagramAnimation = {
	duration: number;
	loop: boolean;
};

// Name of the prop the viewer drives with the animation clock, in seconds.
export const time_prop = 'time';
