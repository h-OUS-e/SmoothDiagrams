/* A small diagram source that follows every source rule, for tests that need a real one. */

export const sample_diagram_source = `<script module>
	export const parameters = [
		{ name: 'ring_count', label: 'Rings', kind: 'number', group: 'general', min: 1, max: 9, step: 1 },
		{ name: 'ink', label: 'Ink', kind: 'color', group: 'styling' }
	];

	export const animation = { duration: 4, loop: true };
</script>

<script>
	let { ring_count = 3, ink = '#1b1d21', time = 0 } = $props();

	let rings = $derived(Array.from({ length: ring_count }, (_, index) => index));
</script>

<svg viewBox="0 0 400 300">
	{#each rings as ring (ring)}
		<circle class="ring" cx="200" cy="150" r={20 + ring * 12 + time} stroke={ink} />
	{/each}
</svg>

<style>
	.ring {
		fill: none;
		stroke-width: 2;
	}
</style>`;

// The sample with its svg element left open, which the compiler rejects.
export const broken_diagram_source = sample_diagram_source.replace('</svg>', '');
