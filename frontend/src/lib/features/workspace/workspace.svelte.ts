/* State of one open project: its pieces, the open piece's tree, the selected node, and a running generation. */

import * as api from '#lib/api/api_client.ts';
import type {
	ModelCatalog,
	ModelOption,
	NodeDetail,
	NodeSummary,
	PieceDetail,
	ProjectDetail,
	StepDetail
} from '#lib/api/api_types.ts';
import {
	open_generation_socket,
	type GenerationEvent,
	type GenerationSocket
} from '#lib/api/generation_socket.ts';
import type {
	DiagramAnimation,
	DiagramParameter,
	ParameterValue,
	ParameterValues
} from '#lib/features/diagram_viewer/diagram_parameters.ts';
import type { ViewerOutcome } from '#lib/features/diagram_viewer/viewer_outcome.ts';

export type ProposedStep = {
	step_token: string;
	source: string;
	step_reasoning: string;
};

export type GenerationState = {
	is_paused: boolean;
	// Step Reasoning of the step being written, as far as it has streamed.
	reasoning_text: string;
	// Step waiting for the viewer to confirm that it renders.
	proposed: ProposedStep | null;
	// Problem with the latest attempt, shown while the model repairs it.
	failure_message: string | null;
};

// Milliseconds to wait after the last control change before storing parameter values.
const save_delay = 400;

// Return the summary of a node, as the piece's tree shows it.
function summarize_node(node: NodeDetail): NodeSummary {
	const accepted_steps = node.steps.filter((step) => !step.is_rejected);
	return {
		id: node.id,
		piece_id: node.piece_id,
		parent_node_id: node.parent_node_id,
		parent_step_id: node.parent_step_id,
		kind: node.kind,
		status: node.status,
		prompt: node.prompt,
		model: node.model,
		is_step_by_step: node.is_step_by_step,
		failure_message: node.failure_message,
		created_at: node.created_at,
		step_count: accepted_steps.length,
		render_svg: accepted_steps.at(-1)?.render_svg ?? null
	};
}

export class Workspace {
	project: ProjectDetail = $state()!;
	piece: PieceDetail | null = $state(null);
	node: NodeDetail | null = $state(null);

	// Null means the newest step, so the selection follows a running generation.
	selected_step_id: string | null = $state(null);

	parameters: DiagramParameter[] = $state.raw([]);
	animation: DiagramAnimation | null = $state.raw(null);
	parameter_values: ParameterValues = $state({});
	time = $state(0);

	generation: GenerationState | null = $state(null);
	is_step_by_step = $state(true);
	model_options: ModelOption[] = $state.raw([]);
	// Id of the model the next generation uses.
	model = $state('');
	error_message: string | null = $state(null);

	accepted_steps: StepDetail[] = $derived(
		this.node?.steps.filter((step) => !step.is_rejected) ?? []
	);
	selected_step: StepDetail | null = $derived(
		this.node?.steps.find((step) => step.id === this.selected_step_id) ??
			this.accepted_steps.at(-1) ??
			null
	);

	// Source on screen: the selected step, or the step a node without steps starts from.
	shown_source: string | null = $derived(
		this.selected_step?.source ?? this.node?.parent_step?.source ?? null
	);
	is_generating = $derived(this.generation !== null);
	selected_model: ModelOption | null = $derived(
		this.model_options.find((option) => option.id === this.model) ?? null
	);

	#socket: GenerationSocket | null = null;
	#save_timer: ReturnType<typeof setTimeout> | null = null;

	constructor(
		project: ProjectDetail,
		piece: PieceDetail | null,
		node: NodeDetail | null,
		model_catalog: ModelCatalog
	) {
		this.project = project;
		this.model_options = model_catalog.models;
		this.model = model_catalog.default_model;
		this.piece = piece;
		this.#show_node(node);
	}

	/* ------------------------------------------------------------------ */
	/* Selection                                                           */
	/* ------------------------------------------------------------------ */

	// Open another piece of the project and select its newest node.
	async open_piece(piece_id: string) {
		if (this.is_generating) return;

		await this.#run(async () => {
			const piece = await api.get_piece(piece_id);
			const newest_node = piece.nodes.at(-1);
			this.piece = piece;
			this.#show_node(newest_node ? await api.get_node(newest_node.id) : null);
		});
	}

	// Select a node of the open piece's tree.
	async select_node(node_id: string) {
		if (this.is_generating || node_id === this.node?.id) return;
		await this.#run(async () => this.#show_node(await api.get_node(node_id)));
	}

	// Select a step of the selected node; the newest one keeps following a generation.
	select_step(step_id: string) {
		this.selected_step_id = step_id === this.accepted_steps.at(-1)?.id ? null : step_id;
	}

	// Add a piece to the project and open it.
	async create_piece() {
		if (this.is_generating) return;

		await this.#run(async () => {
			const piece = await api.create_piece(
				this.project.id,
				`Piece ${this.project.pieces.length + 1}`
			);
			this.project.pieces.push(piece);
			this.piece = { ...piece, nodes: [] };
			this.#show_node(null);
		});
	}

	/* ------------------------------------------------------------------ */
	/* Viewer and controls                                                 */
	/* ------------------------------------------------------------------ */

	// Take the exposed parameters and animation of the diagram that just rendered.
	handle_viewer_outcome = (outcome: ViewerOutcome) => {
		if (!outcome.ok) return;

		this.parameters = outcome.parameters;
		this.animation = outcome.animation;
		this.time = outcome.animation ? Math.min(this.time, outcome.animation.duration) : 0;
	};

	// Change one exposed parameter and store the node's values shortly after.
	set_parameter_value(name: string, value: ParameterValue) {
		const node = this.node;
		if (!node) return;
		this.parameter_values[name] = value;

		if (this.#save_timer) clearTimeout(this.#save_timer);
		this.#save_timer = setTimeout(() => {
			void this.#run(async () => {
				await api.set_parameter_values(node.id, $state.snapshot(this.parameter_values));
			});
		}, save_delay);
	}

	/* ------------------------------------------------------------------ */
	/* Generation                                                          */
	/* ------------------------------------------------------------------ */

	// Start a node from the director's prompt, continuing from the step on screen if there is one.
	start_generation(prompt: string) {
		if (!this.piece || this.generation) return;

		this.error_message = null;
		this.generation = {
			is_paused: false,
			reasoning_text: '',
			proposed: null,
			failure_message: null
		};
		this.#socket = open_generation_socket(
			{
				type: 'start',
				piece_id: this.piece.id,
				parent_step_id: this.selected_step?.id ?? this.node?.parent_step_id ?? null,
				prompt,
				is_step_by_step: this.is_step_by_step,
				model: this.model
			},
			(event) => this.#handle_generation_event(event),
			(has_ended) => this.#handle_socket_closed(has_ended)
		);
	}

	// Report whether the proposed step rendered, so the server can save it or ask for a repair.
	handle_validation_outcome = (outcome: ViewerOutcome) => {
		const proposed = this.generation?.proposed;
		if (!proposed || proposed.source !== outcome.source) return;

		this.#socket?.send({
			type: 'step_outcome',
			step_token: proposed.step_token,
			ok: outcome.ok,
			render_svg: outcome.ok ? outcome.svg_markup : null,
			message: outcome.ok ? null : `Failed at the ${outcome.stage} stage: ${outcome.message}`
		});
	};

	pause() {
		this.#socket?.send({ type: 'pause' });
	}

	resume() {
		this.#socket?.send({ type: 'resume' });
	}

	redirect(prompt: string) {
		this.#socket?.send({ type: 'redirect', prompt });
	}

	reject_latest_step(reason: string | null) {
		this.#socket?.send({ type: 'reject_step', reason });
	}

	stop() {
		this.#socket?.send({ type: 'stop' });
	}

	// Leave the page: stop a running generation by closing its socket.
	dispose() {
		if (this.#save_timer) clearTimeout(this.#save_timer);
		this.#socket?.close();
	}

	// Apply one event of the running generation to the workspace.
	#handle_generation_event(event: GenerationEvent) {
		const generation = this.generation;
		if (!generation) return;

		switch (event.type) {
			case 'node_created':
				this.piece?.nodes.push(summarize_node(event.node));
				this.#show_node(event.node);
				break;
			case 'reasoning_progress':
				generation.reasoning_text = event.text;
				break;
			case 'step_proposed':
				generation.proposed = {
					step_token: event.step_token,
					source: event.source,
					step_reasoning: event.step_reasoning
				};
				generation.reasoning_text = event.step_reasoning;
				break;
			case 'step_saved':
				generation.proposed = null;
				generation.reasoning_text = '';
				generation.failure_message = null;
				this.node?.steps.push(event.step);
				this.#refresh_node_summary();
				break;
			case 'step_failed':
				generation.proposed = null;
				generation.failure_message = event.message;
				break;
			case 'step_rejected': {
				const rejected_step = this.node?.steps.find((step) => step.id === event.step_id);
				if (rejected_step) rejected_step.is_rejected = true;
				if (this.selected_step_id === event.step_id) this.selected_step_id = null;
				generation.proposed = null;
				generation.reasoning_text = '';
				this.#refresh_node_summary();
				break;
			}
			case 'paused':
				generation.is_paused = true;
				break;
			case 'resumed':
				generation.is_paused = false;
				break;
			case 'generation_ended':
				if (this.node) {
					this.node.status = event.status;
					this.node.failure_message = event.message;
				}
				this.#refresh_node_summary();
				this.generation = null;
				break;
		}
	}

	// Recover when the socket closes before the generation reported its end.
	#handle_socket_closed(has_ended: boolean) {
		this.#socket = null;
		if (has_ended || !this.generation) return;

		this.generation = null;
		this.error_message =
			'The connection to the local server was lost. Steps saved so far are kept.';

		// Reload the node, whose status the server settles on its own.
		const node_id = this.node?.id;
		if (node_id) {
			void this.#run(async () => {
				this.node = await api.get_node(node_id);
				this.#refresh_node_summary();
			});
		}
	}

	/* ------------------------------------------------------------------ */
	/* Helpers                                                             */
	/* ------------------------------------------------------------------ */

	// Make a node the selected one and reset everything that belonged to the last one.
	#show_node(node: NodeDetail | null) {
		this.node = node;
		this.selected_step_id = null;
		this.parameter_values = { ...node?.parameter_values };
		this.parameters = [];
		this.animation = null;
		this.time = 0;
	}

	// Bring the selected node's entry in the piece's tree in line with its detail.
	#refresh_node_summary() {
		const node = this.node;
		if (!node || !this.piece) return;

		const index = this.piece.nodes.findIndex((summary) => summary.id === node.id);
		if (index !== -1) this.piece.nodes[index] = summarize_node(node);
	}

	// Run a request and show its error instead of throwing.
	async #run(work: () => Promise<void>) {
		try {
			await work();
		} catch (error) {
			this.error_message = error instanceof Error ? error.message : String(error);
		}
	}
}
