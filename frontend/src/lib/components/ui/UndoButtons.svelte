<script lang="ts">
	import RedoIcon from '#lib/components/icons/RedoIcon.svelte';
	import UndoIcon from '#lib/components/icons/UndoIcon.svelte';
	import Button from './Button.svelte';

	type Props = {
		// What an undo takes back, as in "Undo parameter change".
		subject: string;
		can_undo: boolean;
		can_redo: boolean;
		on_undo: () => void;
		on_redo: () => void;
	};

	let { subject, can_undo, can_redo, on_undo, on_redo }: Props = $props();
</script>

<div class="undo_buttons">
	<Button aria-label="Undo {subject}" title="Undo (Ctrl+Z)" disabled={!can_undo} onclick={on_undo}>
		<UndoIcon size={14} />
	</Button>
	<Button aria-label="Redo {subject}" title="Redo (Ctrl+Y)" disabled={!can_redo} onclick={on_redo}>
		<RedoIcon size={14} />
	</Button>
</div>

<style>
	.undo_buttons {
		display: flex;
		gap: 0.25rem;
	}
</style>
