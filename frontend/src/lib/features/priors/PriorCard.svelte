<script lang="ts">
	import { get_asset_url } from '#lib/api/api_client.ts';
	import type { PriorChanges, PriorDetail } from '#lib/api/api_types.ts';
	import RemoveIcon from '#lib/components/icons/RemoveIcon.svelte';
	import TextAreaField from '#lib/components/ui/TextAreaField.svelte';
	import Toggle from '#lib/components/ui/Toggle.svelte';
	import DiagramThumbnail from '#lib/features/diagram_viewer/DiagramThumbnail.svelte';

	type Props = {
		prior: PriorDetail;
		on_change: (changes: PriorChanges) => void;
		on_remove: () => void;
	};

	let { prior, on_change, on_remove }: Props = $props();

	let item = $derived(prior.library_item);
</script>

<article class={['prior_card', { disabled: !prior.is_enabled }]}>
	<header class="header">
		<h3 class="name">{prior.name}</h3>
		<button
			class="remove"
			type="button"
			aria-label={`Remove ${prior.name} from the priors`}
			onclick={on_remove}
		>
			<RemoveIcon size={12} />
		</button>
	</header>

	<!-- Show what the prior is: the image or diagram it points at, or its own text. -->
	{#if item}
		<div class="thumbnail">
			<DiagramThumbnail
				svg_markup={item.render_svg}
				image_url={item.asset_id ? get_asset_url(item.asset_id) : null}
				label={prior.name}
			/>
		</div>
	{:else}
		<TextAreaField
			label="Text"
			value={prior.text_content ?? ''}
			rows={3}
			on_change={(text_content: string) => on_change({ text_content })}
		/>
	{/if}

	<TextAreaField
		label="Prior note"
		value={prior.prior_note}
		placeholder="What should the model take from this?"
		on_change={(prior_note: string) => on_change({ prior_note })}
	/>
	<Toggle
		label="Use in generations"
		checked={prior.is_enabled}
		on_change={(is_enabled: boolean) => on_change({ is_enabled })}
	/>
</article>

<style>
	.prior_card {
		display: grid;
		gap: 0.5rem;
		padding-bottom: 0.875rem;
		border-bottom: 1px solid var(--color-rule);
	}

	.header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.name {
		min-width: 0;
		margin: 0;
		overflow: hidden;
		font-size: 0.875rem;
		font-weight: 650;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.remove {
		display: grid;
		flex: none;
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

	.thumbnail {
		aspect-ratio: 4 / 3;
		border: 1px solid var(--color-rule);
	}

	.disabled .thumbnail,
	.disabled .name {
		opacity: 0.45;
	}
</style>
