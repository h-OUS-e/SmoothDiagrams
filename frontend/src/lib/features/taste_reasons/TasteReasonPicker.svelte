<script lang="ts">
	import Button from '#lib/components/ui/Button.svelte';

	type Props = {
		// Reasons the taste reason agent offers; empty while it is still working.
		candidates: string[];
		is_loading: boolean;
		on_pick: (taste_reason: string) => void;
		on_dismiss: () => void;
	};

	let { candidates, is_loading, on_pick, on_dismiss }: Props = $props();

	let own_reason = $state('');
	let trimmed_reason = $derived(own_reason.trim());
</script>

<section class="taste_reason_picker" aria-label="Taste reason">
	<h2 class="question">Why did you continue from that one?</h2>

	<!-- Offer the candidate reasons, a field for the director's own, and a way out. -->
	<div class="choices">
		{#if is_loading}
			<p class="waiting">Looking at what you picked.</p>
		{/if}
		{#each candidates as candidate (candidate)}
			<Button variant="marker" onclick={() => on_pick(candidate)}>{candidate}</Button>
		{/each}

		<!-- Use the post method, because the router treats a get form as a navigation. -->
		<form
			class="own"
			method="post"
			onsubmit={(event) => {
				event.preventDefault();
				if (trimmed_reason !== '') on_pick(trimmed_reason);
			}}
		>
			<input
				class="own_reason"
				type="text"
				aria-label="Your own reason"
				placeholder="Another reason"
				bind:value={own_reason}
			/>
			<Button type="submit" disabled={trimmed_reason === ''}>Use mine</Button>
		</form>
		<Button onclick={on_dismiss}>Skip</Button>
	</div>
</section>

<style>
	.taste_reason_picker {
		display: grid;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		border-left: 3px solid var(--color-marker);
		background: var(--color-panel);
	}

	.question {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 700;
		font-stretch: 92%;
	}

	.choices {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.375rem;
	}

	.choices :global(.button) {
		white-space: normal;
		text-align: left;
	}

	.waiting {
		margin: 0;
		color: var(--color-graphite);
	}

	.own {
		display: flex;
		gap: 0.375rem;
	}

	.own_reason {
		width: 12rem;
		min-height: 2rem;
		padding: 0 0.5rem;
		border: 1px solid var(--color-rule);
		border-radius: 2px;
		background: var(--color-paper);
		color: var(--color-ink);
		font: inherit;
	}

	.own_reason::placeholder {
		color: var(--color-graphite);
	}
</style>
