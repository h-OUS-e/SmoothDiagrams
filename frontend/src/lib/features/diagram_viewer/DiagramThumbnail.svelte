<script lang="ts">
	type Props = {
		// Rendered markup of a step, or null when there is nothing to show yet.
		svg_markup: string | null;
		label: string;
	};

	let { svg_markup, label }: Props = $props();

	// Load the markup as an image, which keeps any script inside it from running.
	let image_url = $derived(
		svg_markup === null
			? null
			: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg_markup)}`
	);
</script>

<span class="thumbnail">
	{#if image_url}
		<img class="image" src={image_url} alt={label} />
	{/if}
</span>

<style>
	.thumbnail {
		display: block;
		width: 100%;
		height: 100%;
		background: var(--color-paper);
	}

	.image {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: contain;
	}
</style>
