/* Build the code that runs inside the viewer's sandboxed iframe: the bootstrap plus the Svelte runtime. */

import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig, type Plugin } from 'vite';
import {
	bootstrap_file_name,
	sandbox_modules
} from './src/lib/features/diagram_viewer/sandbox/sandbox_modules.ts';

const module_entry_prefix = 'sandbox_module:';

// Return the entry name for a runtime file, which is its name without the extension.
function entry_name(file_name: string): string {
	return file_name.replace(/\.js$/, '');
}

// Provide one entry per sandbox module that exports everything the module exports.
function sandbox_module_entries(): Plugin {
	return {
		name: 'sandbox_module_entries',
		enforce: 'pre',
		resolveId(id) {
			return id.startsWith(module_entry_prefix) ? `\0${id}` : null;
		},
		load(id) {
			if (!id.startsWith(`\0${module_entry_prefix}`)) return null;
			const specifier = id.slice(module_entry_prefix.length + 1);
			return `export * from ${JSON.stringify(specifier)};`;
		}
	};
}

// Map every sandbox module to its own entry, so all of them share one runtime instance.
const module_entries = Object.fromEntries(
	sandbox_modules.map((module) => [
		entry_name(module.file_name),
		`${module_entry_prefix}${module.specifier}`
	])
);

export default defineConfig({
	plugins: [
		sandbox_module_entries(),
		svelte({ configFile: false, compilerOptions: { runes: true, css: 'injected' } })
	],
	publicDir: false,
	build: {
		outDir: '.sandbox_runtime',
		emptyOutDir: true,
		target: 'es2022',
		modulePreload: false,
		rolldownOptions: {
			input: {
				...module_entries,
				[entry_name(bootstrap_file_name)]: 'src/lib/features/diagram_viewer/sandbox/bootstrap.ts'
			},
			preserveEntrySignatures: 'strict',
			output: {
				format: 'es',
				entryFileNames: '[name].js',
				chunkFileNames: 'chunk_[hash].js'
			}
		}
	}
});
