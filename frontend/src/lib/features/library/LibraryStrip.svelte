<script lang="ts">
	import { get_asset_url, uploadable_image_types } from '#lib/api/api_client.ts';
	import type { LibraryItemDetail, LibraryOrder, LibrarySort } from '#lib/api/api_types.ts';
	import RemoveIcon from '#lib/components/icons/RemoveIcon.svelte';
	import SimilarIcon from '#lib/components/icons/SimilarIcon.svelte';
	import UploadIcon from '#lib/components/icons/UploadIcon.svelte';
	import { drag_source } from '#lib/components/interactions/drag_and_drop.ts';
	import FileButton from '#lib/components/ui/FileButton.svelte';
	import Tabs from '#lib/components/ui/Tabs.svelte';
	import DiagramThumbnail from '#lib/features/diagram_viewer/DiagramThumbnail.svelte';
	import { library_item_drag_kind } from './library_drag.ts';

	type Props = {
		items: LibraryItemDetail[];
		order: LibraryOrder;
		// Whether the items are being loaded in another order, and whether that is taking long.
		is_sorting: boolean;
		is_sort_slow: boolean;
		// Ids of the items the open project already uses as priors.
		used_item_ids: string[];
		on_sort_change: (sort: LibrarySort) => void;
		// Order the items by how much each looks like one of them.
		on_compare: (item_id: string) => void;
		on_add_image: (file: File) => void;
		on_use: (item_id: string) => void;
		on_remove: (item_id: string) => void;
	};

	let {
		items,
		order,
		is_sorting,
		is_sort_slow,
		used_item_ids,
		on_sort_change,
		on_compare,
		on_add_image,
		on_use,
		on_remove
	}: Props = $props();

	const sort_tabs = [
		{ id: 'date', label: 'Newest' },
		{ id: 'name', label: 'Name' },
		{ id: 'similarity', label: 'Similar' }
	] as const;

	let compared_item_id = $derived(order.sort === 'similarity' ? order.similar_to : null);
</script>

<section class="library_strip" aria-label="Library">
	<header class="header">
		<h2 class="title">Library</h2>
		<Tabs
			tabs={sort_tabs}
			selected={order.sort}
			label="Sort the library"
			on_select={(id: LibrarySort) => on_sort_change(id)}
		/>
		<FileButton accept={uploadable_image_types.join(',')} on_pick={on_add_image}>
			<UploadIcon size={14} />
			Add image
		</FileButton>
	</header>

	<!-- Explain a comparison that keeps the director waiting. -->
	{#if is_sort_slow}
		<p class="status" role="status">
			Comparing. The first comparison downloads the similarity model, which can take a minute.
		</p>
	{/if}

	<!-- Show every reference as a tile that can be dragged into the priors or clicked to use. -->
	<ul class="items" aria-busy={is_sorting}>
		{#each items as item (item.id)}
			{@const is_used = used_item_ids.includes(item.id)}
			{@const is_compared = item.id === compared_item_id}
			<li class={['item', { used: is_used, compared: is_compared }]}>
				<button
					class="tile"
					type="button"
					title={is_used
						? `${item.name} is a prior of this project`
						: `Use ${item.name} as a prior`}
					aria-label={is_used
						? `${item.name}, already a prior of this project`
						: `Use ${item.name} as a prior`}
					{@attach drag_source(library_item_drag_kind, item.id)}
					onclick={() => on_use(item.id)}
				>
					<DiagramThumbnail
						svg_markup={item.render_svg}
						image_url={item.asset_id ? get_asset_url(item.asset_id) : null}
						label=""
					/>
				</button>
				<button
					class="action remove"
					type="button"
					title="Remove from the library"
					aria-label={`Remove ${item.name} from the library`}
					onclick={() => on_remove(item.id)}
				>
					<RemoveIcon size={10} />
				</button>
				<button
					class="action compare"
					type="button"
					title="Sort the library by similarity to this"
					aria-label={`Sort the library by similarity to ${item.name}`}
					aria-pressed={is_compared}
					onclick={() => on_compare(item.id)}
				>
					<SimilarIcon size={10} />
				</button>
			</li>
		{:else}
			<li class="empty">
				Add reference images here, or send a diagram from any project. Drag one into Priors to use
				it.
			</li>
		{/each}
	</ul>
</section>

<style>
	.library_strip {
		display: flex;
		align-items: center;
		gap: 1.25rem;
		min-width: 0;
		padding: 0.5rem 1rem;
		background: var(--color-panel);
	}

	.header {
		display: flex;
		flex: none;
		align-items: center;
		gap: 0.875rem;
	}

	.title {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 700;
		font-stretch: 92%;
	}

	.status {
		flex: none;
		max-width: 16rem;
		margin: 0;
		color: var(--color-graphite);
		font-size: 0.8125rem;
	}

	.items {
		display: flex;
		flex: 1;
		gap: 0.375rem;
		min-width: 0;
		margin: 0;
		padding: 0.125rem;
		overflow-x: auto;
		list-style: none;
	}

	.items[aria-busy='true'] {
		opacity: 0.6;
	}

	.item {
		position: relative;
		flex: none;
	}

	.tile {
		display: block;
		width: 4rem;
		height: 3rem;
		padding: 0;
		border: 1px solid var(--color-rule);
		background: var(--color-paper);
		cursor: grab;
	}

	.tile:hover {
		border-color: var(--color-graphite);
	}

	/* Mark a reference this project uses with the director's red. */
	.used .tile {
		border-color: var(--color-marker);
		box-shadow: 0 0 0 1px var(--color-marker);
	}

	/* Mark the reference the others are compared with, apart from whether the project uses it. */
	.compared .tile {
		outline: 2px solid var(--color-ink);
		outline-offset: 1px;
	}

	.compared {
		margin-inline: 3px 0.5rem;
	}

	/* Small round buttons in the corners of a tile, shown when the tile is pointed at. */
	.action {
		position: absolute;
		right: 2px;
		display: grid;
		place-items: center;
		width: 1rem;
		height: 1rem;
		padding: 0;
		border: 0;
		border-radius: 50%;
		background: var(--color-ink);
		color: var(--color-paper);
		opacity: 0;
		cursor: pointer;
	}

	.remove {
		top: 2px;
	}

	.compare {
		bottom: 2px;
	}

	.item:hover .action,
	.action:focus-visible,
	.compare[aria-pressed='true'] {
		opacity: 1;
	}

	.empty {
		align-self: center;
		color: var(--color-graphite);
	}
</style>
