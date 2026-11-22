<script lang="ts">
	import { get_asset_url } from '#lib/api/api_client.ts';
	import type { NodeSummary } from '#lib/api/api_types.ts';
	import DiagramThumbnail from '#lib/features/diagram_viewer/DiagramThumbnail.svelte';
	import { layout_tree } from './tree_layout.ts';

	type Props = {
		nodes: NodeSummary[];
		selected_node_id: string | null;
		// Whether selecting is off, which it is while a generation runs.
		is_locked: boolean;
		on_select: (node_id: string) => void;
	};

	let { nodes, selected_node_id, is_locked, on_select }: Props = $props();

	// Size of one grid cell and of the thumbnail inside it, in pixels.
	const cell_width = 104;
	const cell_height = 70;
	const thumbnail_width = 76;
	const thumbnail_height = 57;

	let layout = $derived(layout_tree(nodes));

	// Return the line from a parent's right edge to its child's left edge, bending once.
	function link_path(parent: { column: number; row: number }, child: typeof parent): string {
		const start_x = parent.column * cell_width + thumbnail_width;
		const start_y = parent.row * cell_height + thumbnail_height / 2;
		const end_x = child.column * cell_width;
		const end_y = child.row * cell_height + thumbnail_height / 2;
		const bend_x = start_x + (cell_width - thumbnail_width) / 2;
		return `M${start_x} ${start_y}H${bend_x}V${end_y}H${end_x}`;
	}

	// Return a short description of a node for assistive technology and the tooltip.
	function describe_node(node: NodeSummary): string {
		if (node.kind === 'uploaded') return 'An edit you uploaded';

		const status = node.status === 'finished' ? '' : ` (${node.status})`;
		const exported = node.export_count > 0 ? ' (exported)' : '';
		return `${node.prompt}${status}${exported}`;
	}
</script>

<section class="piece_tree" aria-label="Nodes of this piece">
	{#if nodes.length === 0}
		<p class="empty">This piece has no diagram yet. Describe one in the prompt box to start.</p>
	{:else}
		<div
			class="grid"
			style:width="{layout.column_count * cell_width}px"
			style:height="{layout.row_count * cell_height}px"
		>
			<!-- Draw the links from each node to the nodes that continue it. -->
			<svg class="links" aria-hidden="true">
				{#each layout.links as link (link.child.node.id)}
					<path d={link_path(link.parent, link.child)} />
				{/each}
			</svg>

			<!-- Show every node as a thumbnail of its newest step. -->
			{#each layout.placements as placement (placement.node.id)}
				<button
					class={[
						'node',
						placement.node.status,
						{
							selected: placement.node.id === selected_node_id,
							exported: placement.node.export_count > 0
						}
					]}
					type="button"
					style:left="{placement.column * cell_width}px"
					style:top="{placement.row * cell_height}px"
					style:width="{thumbnail_width}px"
					style:height="{thumbnail_height}px"
					title={describe_node(placement.node)}
					aria-label={describe_node(placement.node)}
					aria-pressed={placement.node.id === selected_node_id}
					disabled={is_locked && placement.node.id !== selected_node_id}
					onclick={() => on_select(placement.node.id)}
				>
					<DiagramThumbnail
						svg_markup={placement.node.render_svg}
						image_url={placement.node.image_asset_id
							? get_asset_url(placement.node.image_asset_id)
							: null}
						label=""
					/>
				</button>
			{/each}
		</div>
	{/if}
</section>

<style>
	.piece_tree {
		min-width: 0;
		min-height: 0;
		padding: 1rem;
		overflow: auto;
		background: var(--color-panel);
	}

	.empty {
		margin: 0;
		color: var(--color-graphite);
	}

	.grid {
		position: relative;
	}

	.links {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		overflow: visible;
		fill: none;
		stroke: var(--color-graphite);
		stroke-width: 1;
	}

	.node {
		position: absolute;
		padding: 0;
		border: 1px solid var(--color-rule);
		background: var(--color-paper);
		cursor: pointer;
	}

	.node:hover:not(:disabled) {
		border-color: var(--color-graphite);
	}

	.node:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.selected {
		border-color: var(--color-ink);
		box-shadow: 0 0 0 1px var(--color-ink);
	}

	/* Mark a node that is still being drawn with the model's blue. */
	.generating {
		border-style: dashed;
		border-color: var(--color-blueprint);
	}

	/* Mark a node the director exported with a red tab under its thumbnail. */
	.exported::before {
		content: '';
		position: absolute;
		left: -1px;
		bottom: -5px;
		width: 1.25rem;
		height: 4px;
		background: var(--color-marker);
	}

	/* Mark a node whose generation failed with a red corner. */
	.failed::after {
		content: '';
		position: absolute;
		top: 0;
		right: 0;
		border: 5px solid transparent;
		border-top-color: var(--color-marker);
		border-right-color: var(--color-marker);
	}
</style>
