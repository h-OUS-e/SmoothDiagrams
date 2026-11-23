<script lang="ts">
	import type { Snippet } from 'svelte';

	type Props = {
		heading: string;
		children: Snippet;
	};

	let { heading, children }: Props = $props();
</script>

<section class="panel_section">
	<h3 class="heading">{heading}</h3>
	{@render children()}
</section>

<style>
	.panel_section {
		display: grid;
		gap: 0.75rem;
		min-width: 0;
	}

	.heading {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 700;
		font-stretch: 92%;
	}
</style>
