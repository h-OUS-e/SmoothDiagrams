<script lang="ts">
	import type { ModelOption, ModelVendor, PromptControlValue } from '#lib/api/api_types.ts';
	import SelectField from '#lib/components/ui/SelectField.svelte';
	import Toggle from '#lib/components/ui/Toggle.svelte';
	import PromptControlField from './PromptControlField.svelte';
	import type { ProjectInterface } from './project_interface.svelte.ts';

	type Props = {
		project_interface: ProjectInterface;
		model_options: ModelOption[];
		// Whether a generation is running, during which its settings cannot change.
		is_generating: boolean;
	};

	let { project_interface, model_options, is_generating }: Props = $props();

	// Heading the models of each vendor are listed under: the login their calls run on.
	const vendor_headings: Record<ModelVendor, string> = {
		anthropic: 'Claude plan login',
		openai: 'ChatGPT plan login'
	};

	let settings = $derived(project_interface.settings);
	let model_note = $derived(
		model_options.find((option) => option.id === settings.model)?.note ?? null
	);
</script>

<!-- Settings of the project's interface, which apply to every generation. -->
<fieldset class="prompting_controls" disabled={is_generating}>
	<legend class="heading">Prompting</legend>
	<p class="version">Interface version {project_interface.version_number}</p>

	<Toggle
		label="Draw step by step"
		checked={settings.is_step_by_step}
		on_change={(is_step_by_step: boolean) => project_interface.change({ is_step_by_step })}
	/>
	<SelectField
		label="Model"
		value={settings.model}
		options={model_options.map((option) => ({
			value: option.id,
			label: option.label,
			group: vendor_headings[option.vendor]
		}))}
		on_change={(model: string) => project_interface.change({ model })}
	/>
	{#if model_note}
		<p class="model_note">{model_note}</p>
	{/if}
	<Toggle
		label="Offer taste reasons"
		checked={settings.offers_taste_reasons}
		on_change={(offers_taste_reasons: boolean) =>
			project_interface.change({ offers_taste_reasons })}
	/>

	<!-- The prompt controls this interface defines, each told to the model as an instruction. -->
	{#each settings.prompt_controls as control (control.id)}
		<PromptControlField
			{control}
			on_change={(value: PromptControlValue) =>
				project_interface.change_control(control.id, { value })}
		/>
	{/each}
</fieldset>

<style>
	.prompting_controls {
		display: grid;
		gap: 0.75rem;
		margin: 0;
		padding: 0 0 1rem;
		border: 0;
		border-bottom: 1px solid var(--color-rule);
	}

	.heading {
		margin: 0;
		padding: 0;
		font-size: 0.875rem;
		font-weight: 700;
		font-stretch: 92%;
	}

	.version {
		margin: 0;
		color: var(--color-graphite);
		font-size: 0.8125rem;
	}

	.model_note {
		margin: 0;
		color: var(--color-marker);
		font-size: 0.8125rem;
	}
</style>
