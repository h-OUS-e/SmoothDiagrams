<script lang="ts">
	import type { Snippet } from 'svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import TextAreaField from '#lib/components/ui/TextAreaField.svelte';
	import TextField from '#lib/components/ui/TextField.svelte';

	type Props = {
		name_label: string;
		text_label: string;
		text_placeholder: string;
		submit_label: string;
		on_submit: (name: string, text: string) => void;
		// Extra fields shown above the name, such as a choice of kind.
		children?: Snippet;
	};

	let { name_label, text_label, text_placeholder, submit_label, on_submit, children }: Props =
		$props();

	let name = $state('');
	let text = $state('');
	let is_complete = $derived(name.trim() !== '' && text.trim() !== '');

	// Hand over the entry and clear the form for the next one.
	function submit() {
		if (!is_complete) return;

		on_submit(name.trim(), text.trim());
		name = '';
		text = '';
	}
</script>

<!-- Use the post method, because the router treats a get form as a navigation. -->
<form
	class="text_entry_form"
	method="post"
	onsubmit={(event) => {
		event.preventDefault();
		submit();
	}}
>
	{@render children?.()}
	<TextField label={name_label} value={name} on_change={(value: string) => (name = value)} />
	<TextAreaField
		label={text_label}
		value={text}
		placeholder={text_placeholder}
		rows={3}
		on_change={(value: string) => (text = value)}
	/>
	<Button type="submit" disabled={!is_complete}>{submit_label}</Button>
</form>

<style>
	.text_entry_form {
		display: grid;
		gap: 0.5rem;
		justify-items: start;
	}

	.text_entry_form > :global(label) {
		width: 100%;
	}
</style>
