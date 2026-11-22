/* Place the nodes of a piece on a grid: columns run from parent to child, rows separate branches. */

import type { NodeSummary } from '#lib/api/api_types.ts';

export type TreePlacement = {
	node: NodeSummary;
	column: number;
	row: number;
};

export type TreeLink = {
	parent: TreePlacement;
	child: TreePlacement;
};

export type TreeLayout = {
	placements: TreePlacement[];
	links: TreeLink[];
	column_count: number;
	row_count: number;
};

/**
 * Lay out a piece's nodes so the first child continues its parent's row and later children drop below.
 *
 * Args:
 *   nodes: Every node of the piece, oldest first.
 *
 * Returns:
 *   A grid position for every node, the links between them, and the size of the grid.
 */
export function layout_tree(nodes: NodeSummary[]): TreeLayout {
	// Group the nodes by parent; a node whose parent is gone counts as a root.
	const node_ids = new Set(nodes.map((node) => node.id));
	const children_by_parent = new Map<string | null, NodeSummary[]>();
	for (const node of nodes) {
		const parent_id =
			node.parent_node_id !== null && node_ids.has(node.parent_node_id)
				? node.parent_node_id
				: null;
		children_by_parent.set(parent_id, [...(children_by_parent.get(parent_id) ?? []), node]);
	}

	const placements: TreePlacement[] = [];
	const links: TreeLink[] = [];
	let next_row = 0;

	// Place a node on the current row, then its children: the first beside it, the rest below.
	function place(node: NodeSummary, column: number): TreePlacement {
		const placement: TreePlacement = { node, column, row: next_row };
		placements.push(placement);

		const children = children_by_parent.get(node.id) ?? [];
		children.forEach((child, index) => {
			if (index > 0) next_row += 1;
			links.push({ parent: placement, child: place(child, column + 1) });
		});
		return placement;
	}

	// Start every root on a row of its own.
	(children_by_parent.get(null) ?? []).forEach((root, index) => {
		if (index > 0) next_row += 1;
		place(root, 0);
	});

	return {
		placements,
		links,
		column_count: Math.max(0, ...placements.map((placement) => placement.column + 1)),
		row_count: placements.length === 0 ? 0 : next_row + 1
	};
}
