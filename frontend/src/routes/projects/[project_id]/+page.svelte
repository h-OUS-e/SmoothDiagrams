<script lang="ts">
	import { untrack } from 'svelte';
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { get_asset_url } from '#lib/api/api_client.ts';
	import type { LibrarySort, PriorChanges } from '#lib/api/api_types.ts';
	import UploadIcon from '#lib/components/icons/UploadIcon.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import FileButton from '#lib/components/ui/FileButton.svelte';
	import ControlsPanel from '#lib/features/controls/ControlsPanel.svelte';
	import type { ParameterValue } from '#lib/features/diagram_viewer/diagram_parameters.ts';
	import DiagramViewer from '#lib/features/diagram_viewer/DiagramViewer.svelte';
	import {
		read_view_box_size,
		type ViewerExports
	} from '#lib/features/diagram_viewer/viewer_outcome.ts';
	import {
		build_export_file,
		download_file,
		type ExportSettings
	} from '#lib/features/export/export_files.ts';
	import ExportPanel from '#lib/features/export/ExportPanel.svelte';
	import StepRow from '#lib/features/history/StepRow.svelte';
	import LibraryStrip from '#lib/features/library/LibraryStrip.svelte';
	import { ProjectInterface } from '#lib/features/interface/project_interface.svelte.ts';
	import NavigationBar from '#lib/features/navigation/NavigationBar.svelte';
	import PieceTree from '#lib/features/piece_tree/PieceTree.svelte';
	import PlaybackBar from '#lib/features/playback/PlaybackBar.svelte';
	import PriorsPanel from '#lib/features/priors/PriorsPanel.svelte';
	import { References } from '#lib/features/priors/references.svelte.ts';
	import PromptBox from '#lib/features/prompting/PromptBox.svelte';
	import TasteReasonPicker from '#lib/features/taste_reasons/TasteReasonPicker.svelte';
	import StepValidator from '#lib/features/workspace/StepValidator.svelte';
	import { Workspace } from '#lib/features/workspace/workspace.svelte.ts';
	import type { PageProps } from './$types';

	const image_types = 'image/png,image/jpeg,image/gif,image/webp';

	let { data }: PageProps = $props();

	// Build fresh state only when another project is loaded, so a reload of the same
	// project's data never replaces a workspace with a generation running in it.
	let project_id = $derived(data.project.id);
	let page_state = $derived.by(() => {
		void project_id;
		return untrack(() => {
			const project_interface = new ProjectInterface(data.project.id, data.interface_state);
			return {
				project_interface,
				references: new References(data.project.id, data.library, data.priors, data.taste_priors),

				// Reload the versions after a generation, which freezes the version it used.
				workspace: new Workspace(data.project, data.piece, data.node, () => {
					void project_interface.refresh_versions();
				})
			};
		});
	});
	let workspace = $derived(page_state.workspace);
	let references = $derived(page_state.references);
	let project_interface = $derived(page_state.project_interface);

	let error_message = $derived(
		workspace.error_message ?? references.error_message ?? project_interface.error_message
	);

	let viewer: ViewerExports | undefined = $state();

	// Size of the selected step's diagram in its own units, which an exported image is scaled from.
	let diagram_size = $derived(
		workspace.selected_step ? read_view_box_size(workspace.selected_step.render_svg) : null
	);

	// Say in the director's words what a new prompt would start from.
	let starting_point = $derived.by(() => {
		if (workspace.is_uploaded_node) return 'Continue from your edit';

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

	// Store pending interface changes, which the server reads, then start the generation.
	async function start_generation(prompt: string): Promise<boolean> {
		// Do not draw with settings the director did not choose; the failed save shows its error.
		const is_stored = await project_interface.flush();
		if (!is_stored) return false;

		workspace.start_generation(prompt, project_interface.settings.offers_taste_reasons);
		return true;
	}

	// Make the file of an export from the step on screen, save it, and remember the export.
	async function export_diagram(settings: ExportSettings) {
		const step = workspace.selected_step;
		if (!step) return;

		// Fix the values and the time first, so the record matches the file even if a control moves.
		const parameter_values = $state.snapshot(workspace.parameter_values);
		const animation_time = workspace.time;
		const file = await build_export_file({
			...settings,
			source: step.source,
			values: parameter_values,
			capture: () => viewer?.capture() ?? Promise.resolve(null)
		});
		download_file(file);

		await workspace.record_export({
			step_id: step.id,
			format: settings.format,
			parameter_values,
			animation_time,
			pixel_width: file.pixel_size?.width ?? null,
			pixel_height: file.pixel_size?.height ?? null
		});
	}

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

	// Close the socket and drop the waiting saves of state that is being replaced or left.
	$effect(() => {
		const current_workspace = workspace;
		const current_references = references;
		const current_interface = project_interface;
		return () => {
			current_workspace.dispose();
			current_references.dispose();
			current_interface.dispose();
		};
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
		{#if error_message}
			<p class="error" role="alert">{error_message}</p>
		{/if}
	</header>

	<div class="library">
		<LibraryStrip
			items={references.library}
			order={references.library_order}
			is_sorting={references.is_sorting_library}
			is_sort_slow={references.is_library_sort_slow}
			used_item_ids={references.used_item_ids}
			on_sort_change={(sort: LibrarySort) => references.sort_library(sort)}
			on_compare={(item_id: string) => references.compare_library(item_id)}
			on_add_image={(file: File) => references.add_library_image(file)}
			on_use={(item_id: string) => references.use_as_prior(item_id)}
			on_remove={(item_id: string) => references.remove_library_item(item_id)}
		/>
	</div>

	<div class="priors">
		<PriorsPanel
			priors={references.priors}
			taste_priors={references.taste_priors}
			on_use_library_item={(item_id: string) => references.use_as_prior(item_id)}
			on_add_text_prior={(name: string, text: string) => references.add_text_prior(name, text)}
			on_change_prior={(prior_id: string, changes: PriorChanges) =>
				references.change_prior(prior_id, changes)}
			on_remove_prior={(prior_id: string) => references.remove_prior(prior_id)}
			on_add_text_taste_prior={(kind: 'text' | 'skill', name: string, text: string) =>
				references.add_text_taste_prior(kind, name, text)}
			on_add_image_taste_prior={(file: File) => references.add_image_taste_prior(file)}
			disabled_taste_prior_ids={project_interface.settings.disabled_taste_prior_ids}
			on_toggle_taste_prior={(taste_prior_id: string, is_enabled: boolean) =>
				project_interface.set_taste_prior_enabled(taste_prior_id, is_enabled)}
			on_remove_taste_prior={(taste_prior_id: string) =>
				references.remove_taste_prior(taste_prior_id)}
		/>
	</div>

	<main class="stage">
		<!-- Show the diagram of the selected step, the uploaded image, or why there is neither. -->
		<div class="viewer">
			{#if workspace.is_uploaded_node && workspace.node?.image_asset_id}
				<img
					class="uploaded_image"
					src={get_asset_url(workspace.node.image_asset_id)}
					alt="The edit you uploaded"
				/>
			{:else if workspace.shown_source !== null}
				<DiagramViewer
					bind:this={viewer}
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

		{#if workspace.node && !workspace.is_uploaded_node}
			<StepRow
				steps={workspace.node.steps}
				selected_step={workspace.selected_step}
				is_drawing={workspace.is_generating && !workspace.generation?.is_paused}
				drawing_reasoning={workspace.generation?.reasoning_text ?? ''}
				failure_message={workspace.generation?.failure_message ?? null}
				on_select={(step_id: string) => workspace.select_step(step_id)}
			/>
		{/if}

		<!-- Offer what can be done with the node on screen besides prompting. -->
		{#if workspace.node && !workspace.is_generating}
			<div class="node_actions">
				<Button onclick={() => workspace.node && references.add_library_node(workspace.node.id)}>
					Send to Library
				</Button>
				<FileButton accept={image_types} on_pick={(file: File) => workspace.upload_node(file)}>
					<UploadIcon size={14} />
					Upload an edit of this
				</FileButton>
			</div>
		{/if}

		{#if workspace.asks_taste_reason}
			<TasteReasonPicker
				candidates={workspace.node?.taste_reason_candidates ?? []}
				is_loading={workspace.is_offering_taste_reasons}
				on_pick={(taste_reason: string) => workspace.pick_taste_reason(taste_reason)}
				on_dismiss={() => workspace.skip_taste_reason()}
			/>
		{/if}
	</main>

	<div class="controls">
		<ControlsPanel
			parameters={workspace.parameters}
			parameter_values={workspace.parameter_values}
			on_parameter_change={(name: string, value: ParameterValue) =>
				workspace.set_parameter_value(name, value)}
			{project_interface}
			model_options={data.model_catalog.models}
			is_generating={workspace.is_generating}
		>
			{#snippet export_tab()}
				<ExportPanel
					can_export={workspace.can_export}
					{diagram_size}
					default_name={workspace.piece?.name ?? ''}
					exports={workspace.node?.exports ?? []}
					on_export={export_diagram}
				/>
			{/snippet}
		</ControlsPanel>
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
			on_start={start_generation}
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
	/* Page grid: library on top, priors left, viewer center, controls     */
	/* right, tree and prompt below.                                       */
	/* ------------------------------------------------------------------ */

	.project_page {
		display: grid;
		grid-template:
			'top top top' auto
			'library library library' auto
			'priors stage controls' minmax(0, 1fr)
			'tree tree prompt' 13.5rem
			/ 17rem minmax(0, 1fr) 20rem;
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

	.library {
		grid-area: library;
		display: grid;
		min-width: 0;
	}

	.priors {
		grid-area: priors;
		display: grid;
		min-height: 0;
	}

	.stage {
		grid-area: stage;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		min-width: 0;
		min-height: 0;
		padding: 1rem 1.5rem;
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

	.uploaded_image {
		max-width: 100%;
		max-height: 100%;
		min-height: 0;
		object-fit: contain;
		background: var(--color-paper);
		box-shadow:
			0 1px 0 var(--color-rule),
			0 18px 40px -22px rgb(27 29 33 / 0.45);
	}

	.node_actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
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
	@media (max-width: 64rem) {
		.project_page {
			grid-template:
				'top' auto
				'stage' auto
				'prompt' auto
				'controls' auto
				'library' auto
				'priors' auto
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
