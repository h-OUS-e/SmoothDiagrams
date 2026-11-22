<script lang="ts">
	import Field from './Field.svelte';

	type Option = {
		value: string;
		label: string;
		// Heading the option is listed under; options without one are listed first, on their own.
		group?: string;
	};

	type OptionGroup = {
		heading: string | null;
		options: Option[];
	};

	type Props = {
		label: string;
		value: string;
		options: readonly Option[];
		on_change: (value: string) => void;
	};

	let { label, value, options, on_change }: Props = $props();

	// Gather the options under their headings, keeping the order the headings first appear in.
	let option_groups = $derived.by(() => {
		const groups: OptionGroup[] = [];
		for (const option of options) {
			const heading = option.group ?? null;
			const group = groups.find((candidate) => candidate.heading === heading);
			if (group) group.options.push(option);
			else groups.push({ heading, options: [option] });
		}
		return groups;
	});
</script>

{#snippet option_list(listed_options: Option[])}
	{#each listed_options as option (option.value)}
		<option value={option.value}>{option.label}</option>
	{/each}
{/snippet}

<Field {label}>
	<select class="select" {value} onchange={(event) => on_change(event.currentTarget.value)}>
		{#each option_groups as group (group.heading)}
			{#if group.heading === null}
				{@render option_list(group.options)}
			{:else}
				<optgroup label={group.heading}>
					{@render option_list(group.options)}
				</optgroup>
			{/if}
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
