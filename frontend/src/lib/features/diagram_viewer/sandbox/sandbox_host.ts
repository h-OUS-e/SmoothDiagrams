/* What the sandbox host component exposes to the script that mounts it. */

import type { Component } from 'svelte';

export type DiagramProps = Record<string, unknown>;

export type SandboxHostExports = {
	// Replace the mounted diagram and reset the error boundary.
	show_diagram: (next_diagram: Component<DiagramProps>, next_props: DiagramProps) => void;
	// Update the mounted diagram's props without remounting it.
	set_diagram_props: (next_props: DiagramProps) => void;
};
