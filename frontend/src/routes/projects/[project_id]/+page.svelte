<script lang="ts">
	import { untrack } from 'svelte';
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import type { ParameterValue } from '#lib/features/diagram_viewer/diagram_parameters.ts';
	import ControlsPanel from '#lib/features/controls/ControlsPanel.svelte';
	import DiagramViewer from '#lib/features/diagram_viewer/DiagramViewer.svelte';
	import StepRow from '#lib/features/history/StepRow.svelte';
	import NavigationBar from '#lib/features/navigation/NavigationBar.svelte';
	import PieceTree from '#lib/features/piece_tree/PieceTree.svelte';
	import PlaybackBar from '#lib/features/playback/PlaybackBar.svelte';
	import PromptBox from '#lib/features/prompting/PromptBox.svelte';
	import StepValidator from '#lib/features/workspace/StepValidator.svelte';
	import { Workspace } from '#lib/features/workspace/workspace.svelte.ts';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// Build a fresh workspace only when another project is loaded, so a reload of the same
	// project's data never replaces a workspace with a generation running in it.
	let project_id = $derived(data.project.id);
	let workspace = $derived.by(() => {
		void project_id;
		return untrack(() => new Workspace(data.project, data.piece, data.node, data.model_catalog));
	});

	// Say in the director's words what a new prompt would start from.
	let starting_point = $derived.by(() => {
		const step = workspace.selected_step;
		if (!step || step.is_rejected) {
			return workspace.node?.parent_step ? 'Try again from the step before' : 'Start this piece';
		}

		const step_number = workspace.accepted_steps.indexOf(step) + 1;
		const step_count = workspace.accepted_steps.length;
		return step_number === step_count
			? `Continue from step ${step_number}`
			: `Fork from step ${step_number} of ${step_count}`;
	});

	// Open a piece and remember it in the address, so a reload returns to it.
	async function open_piece(piece_id: string) {
		await workspace.open_piece(piece_id);
		remember_open_piece();
	}

	// Add a piece, open it, and remember it in the address.
	async function create_piece() {
		await workspace.create_piece();
		remember_open_piece();
	}

	// Write the open piece into the address without loading the page again.
	function remember_open_piece() {
		if (!workspace.piece) return;

		const query = new URLSearchParams({ [data.piece_parameter]: workspace.piece.id });
		const address = resolve(`/projects/[project_id]?${query.toString()}`, {
			project_id: workspace.project.id
		});
		void replaceState(address, page.state);
	}

	// Close the generation socket of a workspace that is being replaced or left.
	$effect(() => {
		const current_workspace = workspace;
		return () => current_workspace.dispose();
	});
</script>

<svelte:head>
	<title>{workspace.project.name} - SmoothDiagrams</title>
</svelte:head>

<div class="project_page">
	<header class="top">
		<NavigationBar
			project_name={workspace.project.name}
			pieces={workspace.project.pieces}
			open_piece_id={workspace.piece?.id ?? null}
			is_locked={workspace.is_generating}
			on_open_piece={open_piece}
			on_create_piece={create_piece}
		/>
		{#if workspace.error_message}
			<p class="error" role="alert">{workspace.error_message}</p>
		{/if}
	</header>

	<main class="stage">
		<!-- Show the diagram of the selected step, or say why there is none. -->
		<div class="viewer">
			{#if workspace.shown_source !== null}
				<DiagramViewer
					source={workspace.shown_source}
					values={workspace.parameter_values}
					time={workspace.time}
					on_outcome={workspace.handle_viewer_outcome}
				/>
			{:else if workspace.node?.failure_message}
				<div class="notice" role="alert">
					<p class="notice_title">This node has no diagram</p>
					<p>{workspace.node.failure_message}</p>
				</div>
			{:else if workspace.is_generating}
				<p class="notice">The first step appears here as soon as it is drawn.</p>
			{:else}
				<p class="notice">Nothing is drawn yet. Describe a diagram in the prompt box.</p>
			{/if}
		</div>

		{#if workspace.animation && workspace.shown_source !== null}
			<PlaybackBar
				animation={workspace.animation}
				time={workspace.time}
				on_time_change={(time: number) => (workspace.time = time)}
			/>
		{/if}

		{#if workspace.node}
			<StepRow
				steps={workspace.node.steps}
				selected_step={workspace.selected_step}
				is_drawing={workspace.is_generating && !workspace.generation?.is_paused}
				drawing_reasoning={workspace.generation?.reasoning_text ?? ''}
				failure_message={workspace.generation?.failure_message ?? null}
				on_select={(step_id: string) => workspace.select_step(step_id)}
			/>
		{/if}
	</main>

	<div class="controls">
		<ControlsPanel
			parameters={workspace.parameters}
			parameter_values={workspace.parameter_values}
			on_parameter_change={(name: string, value: ParameterValue) =>
				workspace.set_parameter_value(name, value)}
			is_step_by_step={workspace.is_step_by_step}
			on_step_by_step_change={(is_step_by_step: boolean) =>
				(workspace.is_step_by_step = is_step_by_step)}
			model={workspace.model}
			model_options={workspace.model_options}
			model_note={workspace.selected_model?.note ?? null}
			on_model_change={(model: string) => (workspace.model = model)}
			is_generating={workspace.is_generating}
		/>
	</div>

	<div class="tree">
		<PieceTree
			nodes={workspace.piece?.nodes ?? []}
			selected_node_id={workspace.node?.id ?? null}
			is_locked={workspace.is_generating}
			on_select={(node_id: string) => workspace.select_node(node_id)}
		/>
	</div>

	<div class="prompt">
		<PromptBox
			{starting_point}
			is_generating={workspace.is_generating}
			is_paused={workspace.generation?.is_paused ?? false}
			can_reject={workspace.accepted_steps.length > 0}
			on_start={(prompt: string) => workspace.start_generation(prompt)}
			on_redirect={(prompt: string) => workspace.redirect(prompt)}
			on_reject={(reason: string | null) => workspace.reject_latest_step(reason)}
			on_pause={() => workspace.pause()}
			on_resume={() => workspace.resume()}
			on_stop={() => workspace.stop()}
		/>
	</div>
</div>

<StepValidator
	source={workspace.generation?.proposed?.source ?? null}
	on_outcome={workspace.handle_validation_outcome}
/>

<style>
	/* ------------------------------------------------------------------ */
	/* Page grid: viewer in the center, controls right, tree and prompt below. */
	/* ------------------------------------------------------------------ */

	.project_page {
		display: grid;
		grid-template:
			'top top' auto
			'stage controls' minmax(0, 1fr)
			'tree prompt' 13.5rem
			/ minmax(0, 1fr) 20rem;
		gap: 1px;
		height: 100dvh;
	}

	.top {
		grid-area: top;
		display: flex;
		align-items: center;
		justify-content: space-between;
		min-width: 0;
	}

	.stage {
		grid-area: stage;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		min-width: 0;
		min-height: 0;
		padding: 0.5rem 1.5rem 1rem;
	}

	.controls {
		grid-area: controls;
		display: grid;
		min-height: 0;
	}

	.tree {
		grid-area: tree;
		display: grid;
		min-width: 0;
		min-height: 0;
	}

	.prompt {
		grid-area: prompt;
		display: grid;
		min-height: 0;
	}

	/* ------------------------------------------------------------------ */
	/* Stage                                                               */
	/* ------------------------------------------------------------------ */

	.viewer {
		flex: 1;
		display: grid;
		place-items: center;
		min-height: 0;
	}

	.notice {
		max-width: 28rem;
		margin: 0;
		color: var(--color-graphite);
		font-size: 1rem;
		text-align: center;
	}

	.notice_title {
		margin: 0 0 0.25rem;
		color: var(--color-ink);
		font-weight: 700;
	}

	.error {
		margin: 0;
		padding: 0 1rem;
		color: var(--color-marker);
		font-weight: 600;
	}

	/* Stack everything on narrow screens, with the viewer first. */
	@media (max-width: 56rem) {
		.project_page {
			grid-template:
				'top' auto
				'stage' auto
				'prompt' auto
				'controls' auto
				'tree' auto
				/ minmax(0, 1fr);
			height: auto;
		}

		.viewer {
			height: 60vw;
			flex: none;
		}
	}
</style>
