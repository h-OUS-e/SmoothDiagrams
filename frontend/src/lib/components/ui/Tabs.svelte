<script lang="ts" generics="TabId extends string">
	type Tab = {
		id: TabId;
		label: string;
	};

	type Props = {
		tabs: readonly Tab[];
		selected: TabId;
		// Name of the tab group for assistive technology.
		label: string;
		on_select: (id: TabId) => void;
	};

	let { tabs, selected, label, on_select }: Props = $props();
</script>

<div class="tabs" role="tablist" aria-label={label}>
	{#each tabs as tab (tab.id)}
		<button
			class={['tab', { selected: tab.id === selected }]}
			type="button"
			role="tab"
			aria-selected={tab.id === selected}
			onclick={() => on_select(tab.id)}
		>
			{tab.label}
		</button>
	{/each}
</div>

<style>
	.tabs {
		display: flex;
		gap: 1rem;
		border-bottom: 1px solid var(--color-rule);
	}

	.tab {
		margin-bottom: -1px;
		padding: 0.375rem 0;
		border: 0;
		border-bottom: 2px solid transparent;
		background: none;
		color: var(--color-graphite);
		font: inherit;
		font-weight: 600;
		font-stretch: 92%;
		cursor: pointer;
	}

	.tab:hover {
		color: var(--color-ink);
	}

	.selected {
		border-bottom-color: var(--color-ink);
		color: var(--color-ink);
	}
</style>
