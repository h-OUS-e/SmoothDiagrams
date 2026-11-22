<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import type { ParameterValues } from './diagram_parameters.ts';
	import { build_sandbox_document } from './sandbox/sandbox_document.ts';
	import type {
		AppToSandboxMessage,
		RenderFailureStage,
		SandboxToAppMessage
	} from './sandbox/sandbox_messages.ts';

	type Props = {
		code: string | null;
		// Changes for every compile, so the same code can be rendered again.
		render_key: number;
		values: ParameterValues;
		time: number;
		title: string;
		on_rendered: (code: string, svg_markup: string) => void;
		on_failed: (code: string, stage: RenderFailureStage, message: string) => void;
	};

	let { code, render_key, values, time, title, on_rendered, on_failed }: Props = $props();

	let frame: HTMLIFrameElement | undefined = $state();
	let sandbox_document: string | null = $state(null);
	let is_ready = $state(false);

	let last_render_id = 0;
	let rendering_code: string | null = null;
	let last_capture_id = 0;
	// eslint-disable-next-line svelte/prefer-svelte-reactivity -- bookkeeping that is never rendered
	const pending_captures = new Map<number, (svg_markup: string | null) => void>();

	// Build the document in the browser only, because it needs the page's origin.
	onMount(() => {
		sandbox_document = build_sandbox_document(window.location.origin, crypto.randomUUID());
	});

	// Send a message to the sandboxed iframe.
	function post_to_sandbox(message: AppToSandboxMessage) {
		// An opaque-origin iframe can only be addressed with a wildcard target.
		frame?.contentWindow?.postMessage(message, '*');
	}

	// Handle one message from the sandboxed iframe.
	function handle_sandbox_message(event: MessageEvent<SandboxToAppMessage>) {
		if (!frame || event.source !== frame.contentWindow) return;
		const message = event.data;

		switch (message.type) {
			case 'ready':
				is_ready = true;
				break;
			case 'rendered':
				if (message.render_id === last_render_id && rendering_code !== null) {
					on_rendered(rendering_code, message.svg_markup);
				}
				break;
			case 'failed':
				if (message.render_id === last_render_id && rendering_code !== null) {
					on_failed(rendering_code, message.stage, message.message);
				}
				break;
			case 'captured':
				pending_captures.get(message.capture_id)?.(message.svg_markup);
				pending_captures.delete(message.capture_id);
				break;
		}
	}

	// Return the markup of the diagram as it looks right now, or null when none is mounted.
	export function capture(): Promise<string | null> {
		last_capture_id += 1;
		const capture_id = last_capture_id;

		return new Promise((resolve) => {
			pending_captures.set(capture_id, resolve);
			post_to_sandbox({ type: 'capture', capture_id });
		});
	}

	// Render each compile once the sandbox is ready, with the values and time current at that moment.
	$effect(() => {
		void render_key;
		if (!is_ready || code === null) return;

		last_render_id += 1;
		rendering_code = code;
		post_to_sandbox({
			type: 'render',
			render_id: last_render_id,
			code,
			values: untrack(() => $state.snapshot(values)),
			time: untrack(() => time)
		});
	});

	// Push parameter values to the mounted diagram.
	$effect(() => {
		const next_values = $state.snapshot(values);
		if (is_ready) post_to_sandbox({ type: 'set_values', values: next_values });
	});

	// Push the animation clock to the mounted diagram.
	$effect(() => {
		const next_time = time;
		if (is_ready) post_to_sandbox({ type: 'set_time', time: next_time });
	});
</script>

<svelte:window onmessage={handle_sandbox_message} />

<!-- Run the diagram in an iframe with scripts allowed and its own opaque origin. -->
{#if sandbox_document}
	<iframe bind:this={frame} class="frame" {title} sandbox="allow-scripts" srcdoc={sandbox_document}
	></iframe>
{/if}

<style>
	.frame {
		display: block;
		width: 100%;
		height: 100%;
		border: 0;
	}
</style>
