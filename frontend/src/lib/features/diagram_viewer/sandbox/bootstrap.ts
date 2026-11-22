/* Entry script of the sandboxed iframe: mount diagrams sent by the app and report the outcome. */

import { flushSync, mount, type Component } from 'svelte';
import { time_prop, type ParameterValues } from '../diagram_parameters.ts';
import SandboxHost from './SandboxHost.svelte';
import type { DiagramProps, SandboxHostExports } from './sandbox_host.ts';
import type {
	AppToSandboxMessage,
	RenderFailureStage,
	SandboxToAppMessage
} from './sandbox_messages.ts';
import { serialize_svg } from './serialize_svg.ts';

let active_render_id = 0;
let active_render_failed = false;
let module_url: string | null = null;
let values: ParameterValues = {};
let time = 0;

const host: SandboxHostExports = mount(SandboxHost, {
	target: document.body,
	props: { on_render_error: (error: unknown) => report_failure('render', error) }
});

// Send a message to the app that embeds this iframe.
function post_to_app(message: SandboxToAppMessage) {
	// The app's origin is unknown to an opaque-origin iframe, and nothing private is posted.
	window.parent.postMessage(message, '*');
}

// Return a readable message for any thrown value.
function describe_error(error: unknown): string {
	if (error instanceof Error) return error.message;
	return String(error);
}

// Report that the active render failed.
function report_failure(stage: RenderFailureStage, error: unknown) {
	active_render_failed = true;
	post_to_app({
		type: 'failed',
		render_id: active_render_id,
		stage,
		message: describe_error(error)
	});
}

// Return the props the diagram receives: parameter values plus the animation clock.
function build_diagram_props(): DiagramProps {
	return { ...values, [time_prop]: time };
}

// Resolve on a later task, giving errors thrown by pending work time to arrive.
function wait_for_next_task(): Promise<void> {
	// A timer still fires in an iframe that is off screen, where animation frames are paused.
	return new Promise((resolve) => setTimeout(resolve, 0));
}

// Return the markup of the mounted diagram, or null when nothing is mounted.
function capture_svg_markup(): string | null {
	const svg = document.body.querySelector('svg');
	return svg ? serialize_svg(svg) : null;
}

// Load compiled diagram code, mount it, and report whether it rendered.
async function render_diagram(message: Extract<AppToSandboxMessage, { type: 'render' }>) {
	const render_id = message.render_id;
	active_render_id = render_id;
	active_render_failed = false;
	values = message.values;
	time = message.time;

	// Load the code from a blob URL so its bare imports resolve through the import map.
	if (module_url) URL.revokeObjectURL(module_url);
	module_url = URL.createObjectURL(new Blob([message.code], { type: 'text/javascript' }));

	let diagram_module: { default?: unknown };
	try {
		diagram_module = (await import(/* @vite-ignore */ module_url)) as { default?: unknown };
	} catch (error) {
		report_failure('load', error);
		return;
	}

	// Stop when a newer render started while this one was loading.
	if (render_id !== active_render_id) return;

	if (typeof diagram_module.default !== 'function') {
		report_failure('load', new Error('The source has no component to render.'));
		return;
	}

	// Mount the diagram and run its effects, so render errors surface before the check below.
	try {
		host.show_diagram(diagram_module.default as Component<DiagramProps>, build_diagram_props());
		flushSync();
	} catch (error) {
		report_failure('render', error);
		return;
	}
	await wait_for_next_task();
	if (active_render_failed || render_id !== active_render_id) return;

	const svg_markup = capture_svg_markup();
	if (svg_markup === null) {
		report_failure('render', new Error('The diagram rendered no <svg> element.'));
		return;
	}
	post_to_app({ type: 'rendered', render_id, svg_markup });
}

// Handle one message from the app.
function handle_app_message(event: MessageEvent<AppToSandboxMessage>) {
	if (event.source !== window.parent) return;
	const message = event.data;

	switch (message.type) {
		case 'render':
			void render_diagram(message);
			break;
		case 'set_values':
			values = message.values;
			host.set_diagram_props(build_diagram_props());
			break;
		case 'set_time':
			time = message.time;
			host.set_diagram_props(build_diagram_props());
			break;
		case 'capture':
			flushSync();
			post_to_app({
				type: 'captured',
				capture_id: message.capture_id,
				svg_markup: capture_svg_markup()
			});
			break;
	}
}

window.addEventListener('message', handle_app_message);
window.addEventListener('error', (event) =>
	report_failure('runtime', event.error ?? event.message)
);
window.addEventListener('unhandledrejection', (event) => report_failure('runtime', event.reason));

post_to_app({ type: 'ready' });
