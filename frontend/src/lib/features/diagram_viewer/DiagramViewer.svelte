<script lang="ts">
	import { compile_in_worker } from './compiler/compile_client.ts';
	import type {
		DiagramAnimation,
		DiagramParameter,
		ParameterValues
	} from './diagram_parameters.ts';
	import SandboxFrame from './SandboxFrame.svelte';
	import type { RenderFailureStage } from './sandbox/sandbox_messages.ts';
	import {
		read_aspect_ratio,
		type ViewerExports,
		type ViewerFailureStage,
		type ViewerOutcome
	} from './viewer_outcome.ts';

	type Props = {
		source: string | null;
		values: ParameterValues;
		time: number;
		on_outcome: (outcome: ViewerOutcome) => void;
	};

	type CompiledDiagram = {
		source: string;
		code: string;
		parameters: DiagramParameter[];
		animation: DiagramAnimation | null;
	};

	type ViewerFailure = {
		stage: ViewerFailureStage;
		message: string;
	};

	let { source, values, time, on_outcome }: Props = $props();

	let sandbox_frame: ViewerExports | undefined = $state();
	let compiled: CompiledDiagram | null = $state.raw(null);
	let compile_count = $state(0);
	let failure = $state.raw<ViewerFailure | null>(null);
	let aspect_ratio = $state(4 / 3);

	let failure_title = $derived(
		failure?.stage === 'compile' ? 'This source does not compile' : 'This source fails when it runs'
	);

	// Record a failure and tell the owner which source caused it.
	function report_failure(failed_source: string, stage: ViewerFailureStage, message: string) {
		failure = { stage, message };
		on_outcome({ ok: false, source: failed_source, stage, message });
	}

	// Report a diagram that mounted and rendered in the sandbox.
	function handle_rendered(code: string, svg_markup: string) {
		if (compiled?.code !== code) return;

		failure = null;
		aspect_ratio = read_aspect_ratio(svg_markup) ?? aspect_ratio;
		on_outcome({
			ok: true,
			source: compiled.source,
			svg_markup,
			parameters: compiled.parameters,
			animation: compiled.animation
		});
	}

	// Report a diagram that failed to load, render, or keep running in the sandbox.
	function handle_failed(code: string, stage: RenderFailureStage, message: string) {
		if (compiled?.code !== code) return;
		report_failure(compiled.source, stage, message);
	}

	// Return the markup of the diagram as it looks right now, or null when none is shown.
	export function capture(): Promise<string | null> {
		return sandbox_frame?.capture() ?? Promise.resolve(null);
	}

	// Compile the source whenever it changes, keeping the last good diagram on screen meanwhile.
	$effect(() => {
		const next_source = source;
		if (next_source === null) {
			compiled = null;
			failure = null;
			return;
		}

		let is_stale = false;
		void compile_in_worker(next_source).then((outcome) => {
			if (is_stale) return;
			if (outcome.ok) {
				compiled = {
					source: next_source,
					code: outcome.code,
					parameters: outcome.parameters,
					animation: outcome.animation
				};
				compile_count += 1;
			} else {
				report_failure(next_source, 'compile', outcome.message);
			}
		});

		return () => {
			is_stale = true;
		};
	});
</script>

<div class="stage">
	<!-- Show the diagram on a sheet that takes the diagram's own proportions. -->
	<div class="sheet" style:--aspect-ratio={aspect_ratio}>
		<SandboxFrame
			bind:this={sandbox_frame}
			code={compiled?.code ?? null}
			render_key={compile_count}
			{values}
			{time}
			title="Diagram"
			on_rendered={handle_rendered}
			on_failed={handle_failed}
		/>
	</div>

	<!-- Explain why the newest source is not the one on screen. -->
	{#if failure}
		<div class="failure" role="alert">
			<p class="failure_title">{failure_title}</p>
			<pre class="failure_message">{failure.message}</pre>
		</div>
	{/if}
</div>

<style>
	.stage {
		position: relative;
		display: grid;
		place-items: center;
		width: 100%;
		height: 100%;
		container-type: size;
	}

	.sheet {
		width: min(100cqw, 100cqh * var(--aspect-ratio));
		aspect-ratio: var(--aspect-ratio);
		background: var(--color-sheet);
		box-shadow:
			0 1px 0 var(--color-rule),
			0 18px 40px -22px rgb(27 29 33 / 0.45);
	}

	.failure {
		position: absolute;
		inset: auto 0 0 0;
		max-height: 45%;
		overflow: auto;
		padding: 0.75rem 1rem;
		background: var(--color-ink);
		color: var(--color-paper);
	}

	.failure_title {
		margin: 0 0 0.375rem;
		font-weight: 650;
	}

	.failure_message {
		margin: 0;
		font-size: 0.8125rem;
		line-height: 1.45;
		white-space: pre-wrap;
	}
</style>
