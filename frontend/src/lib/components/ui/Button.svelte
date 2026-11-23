<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';

	type Props = HTMLButtonAttributes & {
		// Primary starts the main action, marker carries a director's verdict, quiet does the rest.
		variant?: 'primary' | 'quiet' | 'marker';
		children: Snippet;
	};

	let { variant = 'quiet', type = 'button', children, ...rest }: Props = $props();
</script>

<button class={['button', variant]} {type} {...rest}>
	{@render children()}
</button>

<style>
	.button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.375rem;
		min-height: 2rem;
		padding: 0 0.75rem;
		border: 1px solid var(--color-rule);
		border-radius: 3px;
		background: transparent;
		color: var(--color-ink);
		font: inherit;
		font-weight: 600;
		font-stretch: 92%;
		white-space: nowrap;
		cursor: pointer;
		transition:
			background-color 120ms,
			border-color 120ms;
	}

	.button:hover:not(:disabled) {
		border-color: var(--color-ink);
	}

	.button:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.primary {
		border-color: var(--color-ink);
		background: var(--color-ink);
		color: var(--color-paper);
	}

	.primary:hover:not(:disabled) {
		border-color: var(--color-ink-hover);
		background: var(--color-ink-hover);
	}

	.marker {
		border-color: var(--color-marker);
		color: var(--color-marker);
	}

	.marker:hover:not(:disabled) {
		border-color: var(--color-marker);
		background: var(--color-marker);
		color: var(--color-paper);
	}
</style>
