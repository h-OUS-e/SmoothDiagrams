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
	created_at: string;
};

export type NodeSummary = NodeBase & {
	step_count: number;
	render_svg: string | null;
};

export type NodeDetail = NodeBase & {
	parameter_values: ParameterValues;
	steps: StepDetail[];
	parent_step: StepDetail | null;
};

export type PieceDetail = PieceSummary & {
	nodes: NodeSummary[];
};
