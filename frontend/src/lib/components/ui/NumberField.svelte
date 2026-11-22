<script lang="ts">
	import Field from './Field.svelte';

	type Props = {
		label: string;
		value: number;
		on_change: (value: number) => void;
	};

	let { label, value, on_change }: Props = $props();

	// Pass on only what parses as a number, so a half-typed value changes nothing.
	function handle_input(event: Event & { currentTarget: HTMLInputElement }) {
		const next_value = event.currentTarget.valueAsNumber;
		if (Number.isFinite(next_value)) on_change(next_value);
	}
</script>

<Field {label}>
	<input class="input" type="number" step="any" {value} oninput={handle_input} />
</Field>

<style>
	.input {
		width: 100%;
		min-height: 2rem;
		padding: 0 0.5rem;
		border: 1px solid var(--color-rule);
		border-radius: 2px;
		background: var(--color-paper);
		color: var(--color-ink);
		font: inherit;
		font-variant-numeric: tabular-nums;
	}
</style>
