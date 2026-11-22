<script lang="ts">
	import type { Snippet } from 'svelte';
	import Button from './Button.svelte';

	type Props = {
		// File types the picker offers, as an accept attribute.
		accept: string;
		disabled?: boolean;
		on_pick: (file: File) => void;
		children: Snippet;
	};

	let { accept, disabled = false, on_pick, children }: Props = $props();

	let input: HTMLInputElement | undefined = $state();

	// Hand over the picked file and clear the input, so the same file can be picked again.
	function handle_change() {
		const file = input?.files?.[0];
		if (file) on_pick(file);
		if (input) input.value = '';
	}
</script>

<Button {disabled} onclick={() => input?.click()}>
	{@render children()}
</Button>
<input
	bind:this={input}
	class="input"
	type="file"
	tabindex="-1"
	aria-hidden="true"
	{accept}
	onchange={handle_change}
/>

<style>
	.input {
		display: none;
	}
</style>
