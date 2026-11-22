<script lang="ts">
	import DiagramViewer from '#lib/features/diagram_viewer/DiagramViewer.svelte';
	import type { ViewerOutcome } from '#lib/features/diagram_viewer/viewer_outcome.ts';

	type Props = {
		// Source of the step the model proposed, or null when none is waiting.
		source: string | null;
		on_outcome: (outcome: ViewerOutcome) => void;
	};

	// Check every step with its default values, so the verdict does not depend on the controls.
	const default_values = {};

	let { source, on_outcome }: Props = $props();
</script>

<!-- Render proposed steps off screen, so checking them never disturbs the viewer on screen. -->
<div class="validator" aria-hidden="true">
	<DiagramViewer {source} values={default_values} time={0} {on_outcome} />
</div>

<style>
	.validator {
		position: fixed;
		top: 0;
		left: -10000px;
		width: 800px;
		height: 600px;
		visibility: hidden;
		pointer-events: none;
	}
</style>
