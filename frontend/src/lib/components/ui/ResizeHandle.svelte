<script lang="ts">
	type Props = {
		// Width of the panel in pixels, which dragging and the arrow keys change.
		size: number;
		min_size: number;
		max_size: number;
		// Width a double click returns to.
		default_size: number;
		// Side of the handle the panel is on, which decides the direction that widens it.
		panel_side: 'left' | 'right';
		label: string;
	};

	let { size = $bindable(), min_size, max_size, default_size, panel_side, label }: Props = $props();

	// Pixels one arrow key press moves the edge, and with Shift held.
	const key_step = 16;
	const shift_key_step = 64;

	// Pointer position and panel width when a drag started, or null outside a drag.
	let drag_start: { pointer_x: number; size: number } | null = $state(null);

	// Pointer movement toward the panel shrinks it, and away from it widens it.
	let direction = $derived(panel_side === 'left' ? 1 : -1);

	// Set the width, kept inside its bounds and to whole pixels.
	function resize(next_size: number) {
		size = Math.round(Math.min(max_size, Math.max(min_size, next_size)));
	}

	// Start a drag, holding the pointer so it keeps resizing over iframes and other panels.
	function handle_pointer_down(event: PointerEvent & { currentTarget: HTMLElement }) {
		if (event.button !== 0) return;

		// Stop the drag from selecting text on the page.
		event.preventDefault();
		event.currentTarget.setPointerCapture(event.pointerId);
		drag_start = { pointer_x: event.clientX, size };
	}

	// Resize by how far the pointer moved since the drag started.
	function handle_pointer_move(event: PointerEvent) {
		if (!drag_start) return;
		resize(drag_start.size + (event.clientX - drag_start.pointer_x) * direction);
	}

	function handle_pointer_end() {
		drag_start = null;
	}

	// Resize with the arrow keys, and jump to the bounds with Home and End.
	function handle_key_down(event: KeyboardEvent) {
		const step = event.shiftKey ? shift_key_step : key_step;

		switch (event.key) {
			case 'ArrowRight':
				resize(size + step * direction);
				break;
			case 'ArrowLeft':
				resize(size - step * direction);
				break;
			case 'Home':
				resize(min_size);
				break;
			case 'End':
				resize(max_size);
				break;
			default:
				return;
		}
		event.preventDefault();
	}
</script>

<!-- Follow the window splitter pattern: a focusable separator that reports the panel width. -->
<!-- Ignore the checks that treat every separator as static, since a focusable one is a widget in ARIA. -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
<div
	class={['resize_handle', panel_side, { dragging: drag_start !== null }]}
	role="separator"
	aria-orientation="vertical"
	aria-label={label}
	aria-valuenow={size}
	aria-valuemin={min_size}
	aria-valuemax={max_size}
	tabindex="0"
	onpointerdown={handle_pointer_down}
	onpointermove={handle_pointer_move}
	onpointerup={handle_pointer_end}
	onpointercancel={handle_pointer_end}
	onkeydown={handle_key_down}
	ondblclick={() => resize(default_size)}
></div>

<style>
	/* Sit on the panel edge, which needs a positioned parent around the panel. */
	.resize_handle {
		position: absolute;
		z-index: 1;
		top: 0;
		bottom: 0;
		width: 0.5rem;
		cursor: col-resize;
		touch-action: none;
	}

	.left {
		right: -0.25rem;
	}

	.right {
		left: -0.25rem;
	}

	/* Draw a thin line along the edge, shown on hover, on focus, and during a drag. */
	.resize_handle::after {
		content: '';
		position: absolute;
		top: 0;
		bottom: 0;
		left: calc(50% - 1px);
		width: 2px;
		background: transparent;
		transition: background-color 120ms;
	}

	.resize_handle:hover::after,
	.resize_handle:focus-visible::after {
		background: var(--color-rule);
	}

	.dragging::after {
		background: var(--color-ink);
	}
</style>
