<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PieceSummary } from '#lib/api/api_types.ts';
	import BackIcon from '#lib/components/icons/BackIcon.svelte';
	import PlusIcon from '#lib/components/icons/PlusIcon.svelte';

	type Props = {
		project_name: string;
		pieces: PieceSummary[];
		open_piece_id: string | null;
		// Whether switching is off, which it is while a generation runs.
		is_locked: boolean;
		on_open_piece: (piece_id: string) => void;
		on_create_piece: () => void;
	};

	let { project_name, pieces, open_piece_id, is_locked, on_open_piece, on_create_piece }: Props =
		$props();
</script>

<nav class="navigation_bar" aria-label="Project">
	<a class="home" href={resolve('/')}>
		<BackIcon size={14} />
		Projects
	</a>

	<h1 class="project_name">{project_name}</h1>

	<!-- List the project's pieces, with the open one marked. -->
	<ul class="pieces">
		{#each pieces as piece (piece.id)}
			<li>
				<button
					class={['piece', { open: piece.id === open_piece_id }]}
					type="button"
					aria-current={piece.id === open_piece_id ? 'page' : undefined}
					disabled={is_locked && piece.id !== open_piece_id}
					onclick={() => on_open_piece(piece.id)}
				>
					{piece.name}
				</button>
			</li>
		{/each}
		<li>
			<button
				class="piece add"
				type="button"
				aria-label="Add a piece"
				disabled={is_locked}
				onclick={on_create_piece}
			>
				<PlusIcon size={12} />
			</button>
		</li>
	</ul>
</nav>

<style>
	.navigation_bar {
		display: flex;
		align-items: center;
		gap: 1.25rem;
		min-width: 0;
		padding: 0.625rem 1rem;
	}

	.home {
		display: inline-flex;
		flex: none;
		align-items: center;
		gap: 0.25rem;
		color: var(--color-graphite);
		font-weight: 600;
		font-stretch: 92%;
		text-decoration: none;
	}

	.home:hover {
		color: var(--color-ink);
	}

	.project_name {
		flex: none;
		margin: 0;
		font-size: 1.125rem;
		font-weight: 750;
		font-stretch: 112%;
		letter-spacing: -0.01em;
	}

	.pieces {
		display: flex;
		gap: 0.25rem;
		min-width: 0;
		margin: 0;
		padding: 0;
		overflow-x: auto;
		list-style: none;
	}

	.piece {
		display: grid;
		place-items: center;
		min-height: 1.75rem;
		padding: 0 0.625rem;
		border: 1px solid transparent;
		border-radius: 3px;
		background: none;
		color: var(--color-graphite);
		font: inherit;
		font-weight: 600;
		font-stretch: 92%;
		white-space: nowrap;
		cursor: pointer;
	}

	.piece:hover:not(:disabled) {
		color: var(--color-ink);
	}

	.piece:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.open {
		border-color: var(--color-ink);
		color: var(--color-ink);
	}

	.add {
		border-color: var(--color-rule);
	}
</style>
