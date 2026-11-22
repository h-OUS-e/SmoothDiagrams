<script lang="ts">
	import Field from './Field.svelte';

	type Props = {
		label: string;
		value: string;
		placeholder?: string;
		rows?: number;
		on_change: (value: string) => void;
	};

	let { label, value, placeholder, rows = 2, on_change }: Props = $props();
</script>

<Field {label}>
	<textarea
		class="text"
		{rows}
		{placeholder}
		{value}
		oninput={(event) => on_change(event.currentTarget.value)}></textarea>
</Field>

<style>
	.text {
		width: 100%;
		padding: 0.375rem 0.5rem;
		border: 1px solid var(--color-rule);
		border-radius: 2px;
		background: var(--color-paper);
		color: var(--color-ink);
		font: inherit;
		resize: vertical;
	}

	.text::placeholder {
		color: var(--color-graphite);
	}
</style>
