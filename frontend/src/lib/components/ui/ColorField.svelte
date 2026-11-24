<script lang="ts">
	import Field from './Field.svelte';

	type Props = {
		label: string;
		// Color as #rrggbb.
		value: string;
		on_change: (value: string) => void;
		// Called once the director settles on a color, such as when the picker closes.
		on_change_ended?: () => void;
	};

	let { label, value, on_change, on_change_ended }: Props = $props();
</script>

<Field {label} readout={value} is_inline>
	<input
		class="swatch"
		type="color"
		{value}
		oninput={(event) => on_change(event.currentTarget.value)}
		onchange={() => on_change_ended?.()}
	/>
</Field>

<style>
	.swatch {
		width: 2.25rem;
		height: 1.5rem;
		padding: 0;
		border: 1px solid var(--color-rule);
		border-radius: 2px;
		background: none;
		cursor: pointer;
	}

	.swatch::-webkit-color-swatch-wrapper {
		padding: 2px;
	}

	.swatch::-webkit-color-swatch {
		border: 0;
		border-radius: 1px;
	}

	.swatch::-moz-color-swatch {
		border: 0;
		border-radius: 1px;
	}
</style>
