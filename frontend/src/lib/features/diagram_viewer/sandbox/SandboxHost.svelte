<script lang="ts">
	import type { Component } from 'svelte';
	import type { DiagramProps } from './sandbox_host.ts';

	type Props = {
		on_render_error: (error: unknown) => void;
	};

	let { on_render_error }: Props = $props();

	let Diagram: Component<DiagramProps> | null = $state.raw(null);
	let diagram_props: DiagramProps = $state.raw({});
	let render_count = $state(0);

	// Replace the mounted diagram and reset the error boundary.
	export function show_diagram(next_diagram: Component<DiagramProps>, next_props: DiagramProps) {
		Diagram = next_diagram;
		diagram_props = next_props;
		render_count += 1;
	}

	// Update the mounted diagram's props without remounting it.
	export function set_diagram_props(next_props: DiagramProps) {
		diagram_props = next_props;
	}
</script>

<!-- Render the current diagram inside a boundary that reports render errors. -->
{#key render_count}
	<svelte:boundary onerror={on_render_error}>
		{#if Diagram}
			<Diagram {...diagram_props} />
		{/if}
	</svelte:boundary>
{/key}
