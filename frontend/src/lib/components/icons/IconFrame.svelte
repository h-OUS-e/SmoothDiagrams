<script lang="ts">
	type Props = {
		// Path data drawn on a 16 by 16 grid.
		paths: string[];
		is_filled?: boolean;
		size?: number;
	};

	let { paths, is_filled = false, size = 16 }: Props = $props();
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 16 16"
	fill={is_filled ? 'currentColor' : 'none'}
	stroke={is_filled ? 'none' : 'currentColor'}
	stroke-width="1.5"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	{#each paths as path (path)}
		<path d={path} />
	{/each}
</svg>
