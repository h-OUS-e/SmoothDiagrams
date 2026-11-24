<script lang="ts">
	import { uploadable_image_types } from '#lib/api/api_client.ts';
	import type { PriorChanges, PriorDetail, TastePriorDetail } from '#lib/api/api_types.ts';
	import UploadIcon from '#lib/components/icons/UploadIcon.svelte';
	import { drop_target } from '#lib/components/interactions/drag_and_drop.ts';
	import { read_pasted_image } from '#lib/components/interactions/image_paste.ts';
	import FileButton from '#lib/components/ui/FileButton.svelte';
	import SelectField from '#lib/components/ui/SelectField.svelte';
	import { library_item_drag_kind } from '#lib/features/library/library_drag.ts';
	import PriorCard from './PriorCard.svelte';
	import TastePriorRow from './TastePriorRow.svelte';
	import TextEntryForm from './TextEntryForm.svelte';

	type TextTasteKind = 'text' | 'skill';

	type Props = {
		priors: PriorDetail[];
		taste_priors: TastePriorDetail[];
		// Taste priors the open project's interface switches off.
		disabled_taste_prior_ids: string[];
		on_use_library_item: (item_id: string) => void;
		on_add_image_prior: (file: File) => void;
		on_add_text_prior: (name: string, text: string) => void;
		on_change_prior: (prior_id: string, changes: PriorChanges) => void;
		on_remove_prior: (prior_id: string) => void;
		on_add_text_taste_prior: (kind: TextTasteKind, name: string, text: string) => void;
		on_add_image_taste_prior: (file: File) => void;
		on_toggle_taste_prior: (taste_prior_id: string, is_enabled: boolean) => void;
		on_remove_taste_prior: (taste_prior_id: string) => void;
	};

	let {
		priors,
		taste_priors,
		disabled_taste_prior_ids,
		on_use_library_item,
		on_add_image_prior,
		on_add_text_prior,
		on_change_prior,
		on_remove_prior,
		on_add_text_taste_prior,
		on_add_image_taste_prior,
		on_toggle_taste_prior,
		on_remove_taste_prior
	}: Props = $props();

	const taste_kind_options = [
		{ value: 'text', label: 'Taste notes' },
		{ value: 'skill', label: 'Skill' }
	] as const;

	let taste_kind: TextTasteKind = $state('text');
	let is_taste_form_open = $state(false);

	// Add a pasted image as a taste prior while that form is open, and as a prior otherwise.
	function handle_paste(event: ClipboardEvent) {
		const file = read_pasted_image(event, uploadable_image_types);
		if (!file) return;

		event.preventDefault();
		if (is_taste_form_open) on_add_image_taste_prior(file);
		else on_add_image_prior(file);
	}
</script>

<svelte:window onpaste={handle_paste} />

<!-- Take items dropped from the library anywhere on the panel. -->
<aside
	class="priors_panel"
	aria-label="Priors"
	{@attach drop_target(library_item_drag_kind, on_use_library_item)}
>
	<!-- The project's own priors. -->
	<section class="section">
		<h2 class="title">Priors</h2>
		{#each priors as prior (prior.id)}
			<PriorCard
				{prior}
				on_change={(changes: PriorChanges) => on_change_prior(prior.id, changes)}
				on_remove={() => on_remove_prior(prior.id)}
			/>
		{:else}
			<p class="hint">
				Drag a reference here from the Library, click it there, or paste an image. Each prior can
				carry a note on what to take from it.
			</p>
		{/each}

		<details class="add">
			<summary>Add a text prior</summary>
			<TextEntryForm
				name_label="Name"
				text_label="Text"
				text_placeholder="A brief, a product description, an audience"
				submit_label="Add prior"
				on_submit={on_add_text_prior}
			/>
		</details>
	</section>

	<!-- Taste priors, which apply to every project and can be switched off. -->
	<section class="section">
		<h2 class="title">Taste priors</h2>
		<p class="hint">These guide every project. Switch one off to leave it out of this one.</p>
		<ul class="taste_priors">
			{#each taste_priors as taste_prior (taste_prior.id)}
				<TastePriorRow
					{taste_prior}
					is_enabled={!disabled_taste_prior_ids.includes(taste_prior.id)}
					on_toggle={(is_enabled: boolean) => on_toggle_taste_prior(taste_prior.id, is_enabled)}
					on_remove={() => on_remove_taste_prior(taste_prior.id)}
				/>
			{/each}
		</ul>

		<details class="add" bind:open={is_taste_form_open}>
			<summary>Add a taste prior</summary>
			<TextEntryForm
				name_label="Name"
				text_label="Text"
				text_placeholder="What good looks like to you, or a skill to follow"
				submit_label="Add taste prior"
				on_submit={(name: string, text: string) => on_add_text_taste_prior(taste_kind, name, text)}
			>
				<SelectField
					label="Kind"
					value={taste_kind}
					options={taste_kind_options}
					on_change={(kind: string) => (taste_kind = kind === 'skill' ? 'skill' : 'text')}
				/>
			</TextEntryForm>
			<FileButton accept={uploadable_image_types.join(',')} on_pick={on_add_image_taste_prior}>
				<UploadIcon size={14} />
				Add an image instead
			</FileButton>
			<p class="hint">While this is open, a pasted image becomes a taste prior.</p>
		</details>
	</section>
</aside>

<style>
	.priors_panel {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		min-height: 0;
		padding: 1rem;
		overflow-y: auto;
		background: var(--color-panel);
	}

	/* Keep every column to the panel width, so wide content cannot push it past the edge. */
	.section,
	.taste_priors,
	.add {
		grid-template-columns: minmax(0, 1fr);
	}

	.section {
		display: grid;
		gap: 0.75rem;
	}

	/* Show that a dragged library item can be dropped on the panel. */
	.priors_panel:global(.drop_ready) {
		outline: 2px dashed var(--color-marker);
		outline-offset: -0.375rem;
	}

	.title {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 700;
		font-stretch: 92%;
	}

	.hint {
		margin: 0;
		color: var(--color-graphite);
	}

	.taste_priors {
		display: grid;
		gap: 0.75rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.add {
		display: grid;
		gap: 0.5rem;
	}

	.add > summary {
		color: var(--color-graphite);
		font-weight: 600;
		font-stretch: 92%;
		cursor: pointer;
	}

	.add[open] > summary {
		margin-bottom: 0.5rem;
		color: var(--color-ink);
	}
</style>
