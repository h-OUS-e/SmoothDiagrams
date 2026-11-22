/* Modules available inside the sandbox, shared by the runtime build, the import map, and the compiler. */

export type SandboxModule = {
	specifier: string;
	file_name: string;
};

// Modules a diagram's own source may import.
export const diagram_modules: SandboxModule[] = [
	{ specifier: 'svelte', file_name: 'svelte.js' },
	{ specifier: 'svelte/animate', file_name: 'svelte_animate.js' },
	{ specifier: 'svelte/easing', file_name: 'svelte_easing.js' },
	{ specifier: 'svelte/motion', file_name: 'svelte_motion.js' },
	{ specifier: 'svelte/reactivity', file_name: 'svelte_reactivity.js' },
	{ specifier: 'svelte/transition', file_name: 'svelte_transition.js' }
];

// Modules that only compiled output imports.
export const compiled_output_modules: SandboxModule[] = [
	{ specifier: 'svelte/internal/client', file_name: 'svelte_internal_client.js' },
	{ specifier: 'svelte/internal/init-operations', file_name: 'svelte_internal_init_operations.js' }
];

export const sandbox_modules: SandboxModule[] = [...diagram_modules, ...compiled_output_modules];

export const bootstrap_file_name = 'bootstrap.js';

// Route that serves the built sandbox runtime files.
export const sandbox_runtime_path = '/sandbox_runtime';
