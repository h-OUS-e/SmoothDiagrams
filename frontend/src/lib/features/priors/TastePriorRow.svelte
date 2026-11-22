<script lang="ts">
	import { get_asset_url } from '#lib/api/api_client.ts';
	import type { TastePriorDetail } from '#lib/api/api_types.ts';
	import RemoveIcon from '#lib/components/icons/RemoveIcon.svelte';
	import Toggle from '#lib/components/ui/Toggle.svelte';

	type Props = {
		taste_prior: TastePriorDetail;
		// Whether the open project's interface leaves the taste prior on.
		is_enabled: boolean;
		on_toggle: (is_enabled: boolean) => void;
		on_remove: () => void;
	};

	let { taste_prior, is_enabled, on_toggle, on_remove }: Props = $props();

	const kind_labels = { text: 'Taste notes', skill: 'Skill', image: 'Image' } as const;
</script>

<li class={['taste_prior_row', { disabled: !is_enabled }]}>
	<!-- Show a small preview: the image, or the first lines of the text. -->
	{#if taste_prior.asset_id}
		<img class="preview image" src={get_asset_url(taste_prior.asset_id)} alt="" />
	{:else}
		<p class="preview text">{taste_prior.text_content}</p>
	{/if}

	<div class="switch">
		<Toggle
			label={`${taste_prior.name} (${kind_labels[taste_prior.kind]})`}
			checked={is_enabled}
			on_change={on_toggle}
		/>
	</div>
	<button
		class="remove"
		type="button"
		aria-label={`Remove the taste prior ${taste_prior.name}`}
		onclick={on_remove}
	>
		<RemoveIcon size={12} />
	</button>
</li>

<style>
	.taste_prior_row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 0.25rem 0.5rem;
		align-items: center;
	}

	.switch {
		min-width: 0;
	}

	.preview {
		grid-column: 1 / -1;
		margin: 0;
	}

	.image {
		width: 100%;
		max-height: 5rem;
		border: 1px solid var(--color-rule);
		background: var(--color-paper);
		object-fit: contain;
	}

	.text {
		display: -webkit-box;
		overflow: hidden;
		color: var(--color-graphite);
		font-size: 0.8125rem;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		line-clamp: 2;
	}

	.disabled .preview {
		opacity: 0.45;
	}

	.remove {
		display: grid;
		place-items: center;
		width: 1.25rem;
		height: 1.25rem;
		padding: 0;
		border: 1px solid var(--color-rule);
		border-radius: 50%;
		background: none;
		color: var(--color-graphite);
		cursor: pointer;
	}

	.remove:hover {
		border-color: var(--color-ink);
		color: var(--color-ink);
	}
</style>
