<script lang="ts">
	type Props = {
		// Rendered markup of a step, or null when there is none.
		svg_markup: string | null;
		// Address of an uploaded image, shown when there is no markup.
		image_url?: string | null;
		label: string;
	};

	let { svg_markup, image_url = null, label }: Props = $props();

	// Load the markup as an image, which keeps any script inside it from running.
	let source_url = $derived(
		svg_markup === null
			? image_url
			: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg_markup)}`
	);
</script>

<span class="thumbnail">
	{#if source_url}
		<img class="image" src={source_url} alt={label} draggable="false" />
	{/if}
</span>

<style>
	.thumbnail {
		display: block;
		width: 100%;
		height: 100%;
		background: var(--color-sheet);
	}

	.image {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: contain;
	}
</style>
