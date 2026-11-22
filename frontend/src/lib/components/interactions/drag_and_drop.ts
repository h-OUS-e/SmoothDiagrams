/* Drag a value from one element and drop it on another, as attachments for any element. */

import type { Attachment } from 'svelte/attachments';

// Class a drop target carries while something it accepts is dragged over it.
export const drop_ready_class = 'drop_ready';

// Return the data type that marks a dragged value as one kind of thing from this app.
function drag_type(kind: string): string {
	return `application/x-smooth-diagrams-${kind}`;
}

/**
 * Make an element draggable, carrying a value that only drop targets of the same kind accept.
 *
 * Args:
 *   kind: What is being dragged, such as "library-item".
 *   value: The text a drop target receives, such as an id.
 *
 * Returns:
 *   An attachment for the element to drag.
 */
export function drag_source(kind: string, value: string): Attachment<HTMLElement> {
	return (element) => {
		const handle_drag_start = (event: DragEvent) => {
			event.dataTransfer?.setData(drag_type(kind), value);
			if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy';
		};

		element.draggable = true;
		element.addEventListener('dragstart', handle_drag_start);
		return () => {
			element.draggable = false;
			element.removeEventListener('dragstart', handle_drag_start);
		};
	};
}

/**
 * Let an element receive values dragged from sources of one kind.
 *
 * Args:
 *   kind: What the element accepts, matching the kind of a drag source.
 *   on_drop: Called with the dragged value when it is dropped on the element.
 *
 * Returns:
 *   An attachment for the element to drop on.
 */
export function drop_target(
	kind: string,
	on_drop: (value: string) => void
): Attachment<HTMLElement> {
	return (element) => {
		const accepts = (event: DragEvent) =>
			event.dataTransfer?.types.includes(drag_type(kind)) ?? false;

		// Allow the drop and show that the element is ready for it.
		const handle_drag_over = (event: DragEvent) => {
			if (!accepts(event)) return;
			event.preventDefault();
			element.classList.add(drop_ready_class);
		};

		// Ignore leave events fired when the pointer moves onto a child of the element.
		const handle_drag_leave = (event: DragEvent) => {
			if (event.relatedTarget instanceof Node && element.contains(event.relatedTarget)) return;
			element.classList.remove(drop_ready_class);
		};

		const handle_drop = (event: DragEvent) => {
			if (!accepts(event)) return;
			event.preventDefault();
			element.classList.remove(drop_ready_class);
			on_drop(event.dataTransfer?.getData(drag_type(kind)) ?? '');
		};

		element.addEventListener('dragover', handle_drag_over);
		element.addEventListener('dragleave', handle_drag_leave);
		element.addEventListener('drop', handle_drop);
		return () => {
			element.removeEventListener('dragover', handle_drag_over);
			element.removeEventListener('dragleave', handle_drag_leave);
			element.removeEventListener('drop', handle_drop);
		};
	};
}
