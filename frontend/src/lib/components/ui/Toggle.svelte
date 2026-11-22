<script lang="ts">
	import Field from './Field.svelte';

	type Props = {
		label: string;
		checked: boolean;
		on_change: (checked: boolean) => void;
	};

	let { label, checked, on_change }: Props = $props();
</script>

<Field {label} is_inline>
	<input
		class="toggle"
		type="checkbox"
		role="switch"
		{checked}
		onchange={(event) => on_change(event.currentTarget.checked)}
	/>
</Field>

<style>
	.toggle {
		position: relative;
		width: 2rem;
		height: 1.125rem;
		margin: 0;
		appearance: none;
		border: 1px solid var(--color-graphite);
		border-radius: 999px;
		background: transparent;
		cursor: pointer;
		transition: background-color 120ms;
	}

	.toggle::after {
		content: '';
		position: absolute;
		top: 2px;
		left: 2px;
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 50%;
		background: var(--color-graphite);
		transition: transform 120ms;
	}

	.toggle:checked {
		border-color: var(--color-ink);
		background: var(--color-ink);
	}

	.toggle:checked::after {
		background: var(--color-paper);
		transform: translateX(0.875rem);
	}
</style>
