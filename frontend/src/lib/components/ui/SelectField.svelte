<script lang="ts">
	import Field from './Field.svelte';

	type Option = {
		value: string;
		label: string;
	};

	type Props = {
		label: string;
		value: string;
		options: readonly Option[];
		on_change: (value: string) => void;
	};

	let { label, value, options, on_change }: Props = $props();
</script>

<Field {label}>
	<select class="select" {value} onchange={(event) => on_change(event.currentTarget.value)}>
		{#each options as option (option.value)}
			<option value={option.value}>{option.label}</option>
		{/each}
	</select>
</Field>

<style>
	.select {
		width: 100%;
		min-height: 2rem;
		padding: 0 0.375rem;
		border: 1px solid var(--color-rule);
		border-radius: 2px;
		background: var(--color-paper);
		color: var(--color-ink);
		font: inherit;
	}
</style>
