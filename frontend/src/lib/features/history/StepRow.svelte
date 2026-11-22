<script lang="ts">
	import type { StepDetail } from '#lib/api/api_types.ts';
	import DiagramThumbnail from '#lib/features/diagram_viewer/DiagramThumbnail.svelte';

	type Props = {
		// Every step of the node, rejected ones included.
		steps: StepDetail[];
		selected_step: StepDetail | null;
		// Whether a step is being written right now.
		is_drawing: boolean;
		// Step Reasoning of the step being written, as far as it has streamed.
		drawing_reasoning: string;
		// Problem with the latest attempt, while the model repairs it.
		failure_message: string | null;
		on_select: (step_id: string) => void;
	};

	let { steps, selected_step, is_drawing, drawing_reasoning, failure_message, on_select }: Props =
		$props();

	// Number the steps that were kept; a rejected step has no number.
	let numbered_steps = $derived.by(() => {
		let number = 0;
		return steps.map((step) => ({ step, number: step.is_rejected ? null : (number += 1) }));
	});
	let next_number = $derived(numbered_steps.filter((entry) => entry.number !== null).length + 1);
	let is_following = $derived(
		is_drawing && selected_step?.id === steps.findLast((step) => !step.is_rejected)?.id
	);
</script>

<div class="step_row">
	<!-- Show one frame per step, in the order the steps were drawn. -->
	<ol class="frames">
		{#each numbered_steps as { step, number } (step.id)}
			<li>
				<button
					class={['frame', { selected: step.id === selected_step?.id, rejected: step.is_rejected }]}
					type="button"
					aria-pressed={step.id === selected_step?.id}
					title={step.is_rejected ? `Rejected: ${step.step_reasoning}` : step.step_reasoning}
					onclick={() => on_select(step.id)}
				>
					<DiagramThumbnail
						svg_markup={step.render_svg}
						label={number === null ? 'Rejected step' : `Step ${number}`}
					/>
					<span class="number">{number ?? 'Rejected'}</span>
				</button>
			</li>
		{/each}

		{#if is_drawing}
			<li class="frame drawing" aria-label={`Drawing step ${next_number}`}>
				<span class="number">{next_number}</span>
			</li>
		{/if}
	</ol>

	<!-- Show the reasoning of the step being drawn, or of the selected step. -->
	<p class="reasoning" aria-live="polite">
		{#if failure_message && is_drawing}
			<span class="repair">Repairing a step that did not render.</span>
		{:else if (is_following || !selected_step) && is_drawing}
			{drawing_reasoning || 'Thinking about the next step.'}
		{:else if selected_step}
			{selected_step.step_reasoning}
			{#if selected_step.is_rejected && selected_step.rejection_reason}
				<span class="rejection">You rejected it: {selected_step.rejection_reason}</span>
			{/if}
		{/if}
	</p>
</div>

<style>
	.step_row {
		display: grid;
		gap: 0.5rem;
		min-width: 0;
	}

	.frames {
		display: flex;
		gap: 0.375rem;
		margin: 0;
		padding: 0.25rem 0.125rem;
		overflow-x: auto;
		list-style: none;
	}

	.frame {
		position: relative;
		display: block;
		flex: none;
		width: 4.5rem;
		height: 3.375rem;
		padding: 0;
		border: 1px solid var(--color-rule);
		background: var(--color-paper);
		cursor: pointer;
	}

	.frame:hover {
		border-color: var(--color-graphite);
	}

	.selected {
		border-color: var(--color-ink);
		box-shadow: 0 0 0 1px var(--color-ink);
	}

	.rejected {
		opacity: 0.55;
	}

	/* Strike a rejected step with the director's red. */
	.rejected::after {
		content: '';
		position: absolute;
		inset: 0;
		background: linear-gradient(
			to top right,
			transparent calc(50% - 1px),
			var(--color-marker) calc(50% - 1px),
			var(--color-marker) calc(50% + 1px),
			transparent calc(50% + 1px)
		);
	}

	.drawing {
		border-style: dashed;
		border-color: var(--color-blueprint);
		background: var(--color-blueprint-wash);
		cursor: default;
	}

	.number {
		position: absolute;
		left: 0;
		bottom: 0;
		padding: 0 0.25rem;
		background: var(--color-paper);
		color: var(--color-graphite);
		font-size: 0.6875rem;
		font-weight: 600;
		font-stretch: 85%;
		font-variant-numeric: tabular-nums;
	}

	.drawing .number {
		background: none;
		color: var(--color-blueprint);
	}

	.reasoning {
		min-height: 2.8em;
		margin: 0;
		color: var(--color-blueprint);
		font-family: var(--font-note);
		font-size: 1rem;
		font-style: italic;
		line-height: 1.4;
	}

	.repair {
		color: var(--color-graphite);
	}

	.rejection {
		display: block;
		color: var(--color-marker);
		font-family: var(--font-sans);
		font-size: 0.8125rem;
		font-style: normal;
	}
</style>
