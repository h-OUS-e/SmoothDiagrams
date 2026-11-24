<script lang="ts">
	import Field from './Field.svelte';

	type Props = {
		label: string;
		value: number;
		min: number;
		max: number;
		step: number;
		on_change: (value: number) => void;
		// Called once the director releases the slider or stops stepping it with the keyboard.
		on_change_ended?: () => void;
	};

	let { label, value, min, max, step, on_change, on_change_ended }: Props = $props();

	// Show as many decimals as the step has, so the readout does not jitter.
	let decimals = $derived(String(step).split('.')[1]?.length ?? 0);
</script>

<Field {label} readout={value.toFixed(decimals)}>
	<input
		class="slider"
		type="range"
		{min}
		{max}
		{step}
		{value}
		oninput={(event) => on_change(event.currentTarget.valueAsNumber)}
		onchange={() => on_change_ended?.()}
	/>
</Field>

<style>
	.slider {
		width: 100%;
		height: 1.25rem;
		margin: 0;
		appearance: none;
		background: transparent;
		cursor: pointer;
	}

	.slider::-webkit-slider-runnable-track {
		height: 2px;
		background: var(--color-rule);
	}

	.slider::-moz-range-track {
		height: 2px;
		background: var(--color-rule);
	}

	.slider::-webkit-slider-thumb {
		width: 0.5rem;
		height: 1rem;
		margin-top: calc(-0.5rem + 1px);
		appearance: none;
		border-radius: 1px;
		background: var(--color-ink);
	}

	.slider::-moz-range-thumb {
		width: 0.5rem;
		height: 1rem;
		border: 0;
		border-radius: 1px;
		background: var(--color-ink);
	}
</style>
