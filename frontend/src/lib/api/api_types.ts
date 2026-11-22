/* Shapes of the data the local server sends. Keep in step with backend/smooth_diagrams/schemas.py. */

import type { ParameterValues } from '#lib/features/diagram_viewer/diagram_parameters.ts';

export type NodeKind = 'generated' | 'uploaded';

export type NodeStatus = 'generating' | 'finished' | 'stopped' | 'failed';

export type ModelOption = {
	// Exact model id, which the label names with its version.
	id: string;
	label: string;
	// Something the director should know before choosing the model.
	note: string | null;
};

export type ModelCatalog = {
	default_model: string;
	models: ModelOption[];
};

export type PieceSummary = {
	id: string;
	project_id: string;
	name: string;
	created_at: string;
};

export type ProjectSummary = {
	id: string;
	name: string;
	created_at: string;
	piece_count: number;
	cover_svg: string | null;
};

export type ProjectDetail = {
	id: string;
	name: string;
	created_at: string;
	pieces: PieceSummary[];
};

export type StepDetail = {
	id: string;
	node_id: string;
	step_index: number;
	source: string;
	step_reasoning: string;
	render_svg: string;
	is_rejected: boolean;
	rejection_reason: string | null;
	created_at: string;
};

export type ExportFormat = 'svelte' | 'svg' | 'png' | 'jpeg';

// What an export was made from: a step, as it looked with these values at this time.
export type ExportInput = {
	step_id: string;
	format: ExportFormat;
	parameter_values: ParameterValues;
	// Animation clock in seconds.
	animation_time: number;
	// Size of a PNG or JPEG in pixels; null for the formats that have no fixed size.
	pixel_width: number | null;
	pixel_height: number | null;
};

export type ExportDetail = Omit<ExportInput, 'step_id'> & {
	id: string;
	node_id: string;
	// Null once the exported step is gone.
	step_id: string | null;
	created_at: string;
};

type NodeBase = {
	id: string;
	piece_id: string;
	parent_node_id: string | null;
	parent_step_id: string | null;
	kind: NodeKind;
	status: NodeStatus;
	prompt: string;
	model: string | null;
	is_step_by_step: boolean;
	failure_message: string | null;
	// Image an uploaded node holds instead of source.
	image_asset_id: string | null;
	// Interface version whose settings made the node.
	interface_version_id: string | null;
	created_at: string;
};

export type NodeSummary = NodeBase & {
	step_count: number;
	render_svg: string | null;
	// Number of times the node was exported.
	export_count: number;
};

export type NodeDetail = NodeBase & {
	// Reasons offered for continuing from the parent node, and the one the director picked.
	taste_reason_candidates: string[] | null;
	taste_reason: string | null;
	parameter_values: ParameterValues;
	steps: StepDetail[];
	parent_step: StepDetail | null;
	exports: ExportDetail[];
};

export type PieceDetail = PieceSummary & {
	nodes: NodeSummary[];
};

export type LibraryItemKind = 'image' | 'node';

export type LibraryItemDetail = {
	id: string;
	kind: LibraryItemKind;
	name: string;
	// Image of an image item, or of a node item whose node was uploaded.
	asset_id: string | null;
	node_id: string | null;
	created_at: string;
	// Render of the newest step of a node item.
	render_svg: string | null;
};

export type LibrarySort = 'date' | 'name' | 'similarity';

// How the library is ordered; similarity is measured against one of its items.
export type LibraryOrder =
	{ sort: Exclude<LibrarySort, 'similarity'> } | { sort: 'similarity'; similar_to: string };

export type PriorDetail = {
	id: string;
	project_id: string;
	name: string;
	// Text of a text prior; null for a prior that points at a library item.
	text_content: string | null;
	library_item: LibraryItemDetail | null;
	prior_note: string;
	is_enabled: boolean;
	created_at: string;
};

export type PriorChanges = {
	name?: string;
	text_content?: string;
	prior_note?: string;
	is_enabled?: boolean;
};

export type TastePriorKind = 'text' | 'image' | 'skill';

export type TastePriorDetail = {
	id: string;
	kind: TastePriorKind;
	name: string;
	text_content: string | null;
	asset_id: string | null;
	created_at: string;
};

export type TastePriorChanges = {
	name?: string;
	text_content?: string;
};

export type PromptControlKind = 'slider' | 'select' | 'toggle' | 'text';

export type PromptControlValue = number | string | boolean;

// A control the director sets, whose value is told to the model as an instruction.
export type PromptControl = {
	id: string;
	label: string;
	kind: PromptControlKind;
	// What the model is told; "{value}" stands for the control's value.
	instruction: string;
	value: PromptControlValue;
	// Range of a slider.
	min: number | null;
	max: number | null;
	step: number | null;
	// Choices of a select.
	options: string[] | null;
};

export type PromptTemplates = {
	// Standing instructions for every generation of the project.
	direction: string;
	step_by_step: string;
	single_pass: string;
};

export type InterfaceSettings = {
	model: string;
	is_step_by_step: boolean;
	offers_taste_reasons: boolean;
	prompt_templates: PromptTemplates;
	prompt_controls: PromptControl[];
	// Taste priors switched off for the project; every other taste prior applies.
	disabled_taste_prior_ids: string[];
};

export type InterfaceVersionSummary = {
	id: string;
	version_number: number;
	created_at: string;
	// Number of nodes made with the version.
	node_count: number;
	is_current: boolean;
};

export type InterfaceState = {
	current_version_id: string;
	version_number: number;
	settings: InterfaceSettings;
	versions: InterfaceVersionSummary[];
};

// An interface version a new project can start from.
export type InterfaceSource = {
	id: string;
	project_id: string;
	project_name: string;
	version_number: number;
	created_at: string;
};
