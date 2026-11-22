<script lang="ts">
	import type { Snippet } from 'svelte';

	type Props = {
		label: string;
		// Current value shown beside the label, for controls that do not show it themselves.
		readout?: string;
		// Put the control beside the label instead of under it.
		is_inline?: boolean;
		children: Snippet;
	};

	let { label, readout, is_inline = false, children }: Props = $props();
</script>

<label class={['field', { inline: is_inline }]}>
	<span class="heading">
		<span class="label">{label}</span>
		{#if readout !== undefined}
			<span class="readout">{readout}</span>
		{/if}
	</span>
	{@render children()}
</label>

<style>
	.field {
		display: grid;
		gap: 0.25rem;
	}

	.inline {
		grid-template-columns: 1fr auto;
		align-items: center;
	}

	.heading {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.label {
		color: var(--color-graphite);
		font-size: 0.8125rem;
		font-weight: 550;
		font-stretch: 88%;
	}

	.readout {
		font-size: 0.8125rem;
		font-variant-numeric: tabular-nums;
	}
</style>
