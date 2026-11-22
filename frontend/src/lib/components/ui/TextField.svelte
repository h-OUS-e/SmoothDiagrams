<script lang="ts">
	import Field from './Field.svelte';

	type Props = {
		label: string;
		value: string;
		on_change: (value: string) => void;
	};

	let { label, value, on_change }: Props = $props();
</script>

<Field {label}>
	<input
		class="input"
		type="text"
		{value}
		oninput={(event) => on_change(event.currentTarget.value)}
	/>
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
	}
</style>
