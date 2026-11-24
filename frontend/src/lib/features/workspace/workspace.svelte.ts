/* State of one open project: its pieces, the open piece's tree, the selected node, and a running generation. */

import * as api from '#lib/api/api_client.ts';
import type {
	ExportInput,
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
import { UndoStack } from '#lib/state/undo_stack.svelte.ts';

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
		image_asset_id: node.image_asset_id,
		interface_version_id: node.interface_version_id,
		created_at: node.created_at,
		step_count: accepted_steps.length,
		render_svg: accepted_steps.at(-1)?.render_svg ?? null,
		export_count: node.exports.length
	};
}

// Return whether two sets of parameter values hold the same value for every parameter.
function are_parameter_values_equal(first: ParameterValues, second: ParameterValues): boolean {
	const names = new Set([...Object.keys(first), ...Object.keys(second)]);
	return [...names].every((name) => first[name] === second[name]);
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
	// Earlier and undone parameter values of the selected node, emptied when another node is selected.
	parameter_history = new UndoStack<ParameterValues>();
	time = $state(0);

	// Source of the diagram the viewer shows, which stays the last good one when a source fails.
	rendered_source: string | null = $state(null);

	generation: GenerationState | null = $state(null);
	error_message: string | null = $state(null);

	is_offering_taste_reasons = $state(false);
	// Ids of the nodes whose taste reason question the director skipped in this visit.
	skipped_taste_reason_node_ids: string[] = $state([]);

	accepted_steps: StepDetail[] = $derived(
		this.node?.steps.filter((step) => !step.is_rejected) ?? []
	);
	selected_step: StepDetail | null = $derived(
		this.node?.steps.find((step) => step.id === this.selected_step_id) ??
			this.accepted_steps.at(-1) ??
			null
	);

	is_uploaded_node = $derived(this.node?.kind === 'uploaded');

	// Source on screen: the selected step, or the step a node without steps starts from.
	shown_source: string | null = $derived(
		this.is_uploaded_node
			? null
			: (this.selected_step?.source ?? this.node?.parent_step?.source ?? null)
	);
	is_generating = $derived(this.generation !== null);

	// Whether the viewer shows the selected step, so that what is exported is what is on screen.
	can_export = $derived(
		this.selected_step !== null && this.rendered_source === this.selected_step.source
	);

	// Whether to ask why the director continued from the selected node's parent.
	asks_taste_reason = $derived.by(() => {
		const node = this.node;
		if (!node || node.parent_node_id === null || node.taste_reason !== null) return false;
		if (this.skipped_taste_reason_node_ids.includes(node.id)) return false;
		return this.is_offering_taste_reasons || (node.taste_reason_candidates?.length ?? 0) > 0;
	});

	#socket: GenerationSocket | null = null;
	#save_timer: ReturnType<typeof setTimeout> | null = null;
	// Parameter values before the change in progress, or null when no change is in progress.
	#values_before_change: ParameterValues | null = null;
	#offers_taste_reasons = false;
	#on_generation_ended: () => void;

	constructor(
		project: ProjectDetail,
		piece: PieceDetail | null,
		node: NodeDetail | null,
		// Called whenever a generation ends, however it ends.
		on_generation_ended: () => void
	) {
		this.project = project;
		this.#on_generation_ended = on_generation_ended;
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

		this.rendered_source = outcome.source;
		this.parameters = outcome.parameters;
		this.animation = outcome.animation;
		this.time = outcome.animation ? Math.min(this.time, outcome.animation.duration) : 0;
	};

	// Change one exposed parameter and store the node's values shortly after.
	set_parameter_value(name: string, value: ParameterValue) {
		if (!this.node) return;

		// Keep the values from before the first change of a drag or typing, for undo.
		this.#values_before_change ??= $state.snapshot(this.parameter_values);

		this.parameter_values[name] = value;
		this.#schedule_parameter_save();
	}

	// Record the change in progress as one step of undo, unless it left the values as they were.
	end_parameter_change() {
		const values_before_change = this.#values_before_change;
		if (!values_before_change) return;
		this.#values_before_change = null;

		if (are_parameter_values_equal(values_before_change, this.parameter_values)) return;
		this.parameter_history.record(values_before_change);
	}

	// Go back to the parameter values before the last change.
	undo_parameter_change() {
		this.end_parameter_change();
		const previous_values = this.parameter_history.undo($state.snapshot(this.parameter_values));
		if (previous_values) this.#replace_parameter_values(previous_values);
	}

	// Bring back the parameter values the last undo took away.
	redo_parameter_change() {
		this.end_parameter_change();
		const next_values = this.parameter_history.redo($state.snapshot(this.parameter_values));
		if (next_values) this.#replace_parameter_values(next_values);
	}

	// Remember an export of the selected node and mark the node as exported in the tree.
	async record_export(export_input: ExportInput) {
		const node = this.node;
		if (!node) return;

		await this.#run(async () => {
			node.exports.push(await api.add_export(node.id, export_input));
			this.#refresh_node_summary();
		});
	}

	/* ------------------------------------------------------------------ */
	/* Generation                                                          */
	/* ------------------------------------------------------------------ */

	// Add an image the director edited outside the app as a node under the step on screen.
	async upload_node(file: File) {
		const piece = this.piece;
		if (!piece || this.is_generating) return;

		await this.#run(async () => {
			const parent_step_id = this.selected_step?.id ?? this.node?.parent_step_id ?? null;
			const node = await api.add_uploaded_node(piece.id, file, parent_step_id);
			piece.nodes.push(summarize_node(node));
			this.#show_node(node);
		});
	}

	// Store the reason the director picked or wrote for continuing from the parent node.
	async pick_taste_reason(taste_reason: string) {
		const node = this.node;
		if (!node) return;

		node.taste_reason = taste_reason;
		await this.#run(async () => {
			await api.set_taste_reason(node.id, taste_reason);
		});
	}

	// Stop asking for the selected node's taste reason; its candidates stay stored.
	skip_taste_reason() {
		if (this.node) this.skipped_taste_reason_node_ids.push(this.node.id);
	}

	/**
	 * Start a node from the director's prompt, continuing from the step on screen if there is one.
	 *
	 * The server reads everything else from the project's interface, so its pending changes
	 * must be stored before this is called.
	 *
	 * Args:
	 *   prompt: What the director asks for.
	 *   offers_taste_reasons: Whether to ask the taste reason agent about the new node.
	 */
	start_generation(prompt: string, offers_taste_reasons: boolean) {
		if (!this.piece || this.generation) return;
		this.#offers_taste_reasons = offers_taste_reasons;

		// Continue from a step, or from an uploaded node, which has no step to name.
		const parent_step_id = this.is_uploaded_node
			? null
			: (this.selected_step?.id ?? this.node?.parent_step_id ?? null);
		const uploaded_parent_id = this.is_uploaded_node ? this.node?.id : this.node?.parent_node_id;
		const parent_node_id = parent_step_id === null ? (uploaded_parent_id ?? null) : null;

		this.error_message = null;
		this.generation = {
			is_paused: false,
			reasoning_text: '',
			proposed: null,
			failure_message: null
		};

		// Ignore this socket once another is current, because a socket closes after its generation.
		const socket = open_generation_socket(
			{
				type: 'start',
				piece_id: this.piece.id,
				parent_step_id,
				parent_node_id,
				prompt
			},
			(event) => {
				if (this.#socket === socket) this.#handle_generation_event(event);
			},
			(has_ended) => {
				if (this.#socket === socket) this.#handle_socket_closed(has_ended);
			}
		);
		this.#socket = socket;
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
				if (this.#offers_taste_reasons && event.node.parent_node_id !== null) {
					void this.#offer_taste_reasons(event.node.id);
				}
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
				this.#on_generation_ended();
				break;
		}
	}

	// Ask the taste reason agent about a new node and attach its candidates to the node.
	async #offer_taste_reasons(node_id: string) {
		this.is_offering_taste_reasons = true;
		await this.#run(async () => {
			const candidates = await api.offer_taste_reasons(node_id);
			if (this.node?.id === node_id) this.node.taste_reason_candidates = candidates;
		});
		this.is_offering_taste_reasons = false;
	}

	// Recover when the socket closes before the generation reported its end.
	#handle_socket_closed(has_ended: boolean) {
		this.#socket = null;
		if (has_ended || !this.generation) return;

		this.generation = null;
		this.#on_generation_ended();
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
		this.parameter_history.clear();
		this.#values_before_change = null;
		this.parameters = [];
		this.animation = null;
		this.time = 0;
		this.rendered_source = null;
	}

	// Show other parameter values on the selected node and store them shortly after.
	#replace_parameter_values(parameter_values: ParameterValues) {
		if (!this.node) return;
		// Copy the values, so later changes never reach the state kept in the undo stack.
		this.parameter_values = { ...parameter_values };
		this.#schedule_parameter_save();
	}

	// Store the selected node's parameter values once the controls rest for a moment.
	#schedule_parameter_save() {
		const node = this.node;
		if (!node) return;

		if (this.#save_timer) clearTimeout(this.#save_timer);
		this.#save_timer = setTimeout(() => {
			void this.#run(async () => {
				await api.set_parameter_values(node.id, $state.snapshot(this.parameter_values));
			});
		}, save_delay);
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
