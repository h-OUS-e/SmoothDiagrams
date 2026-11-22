<script lang="ts">
	import SelectField from '#lib/components/ui/SelectField.svelte';
	import Tabs from '#lib/components/ui/Tabs.svelte';
	import Toggle from '#lib/components/ui/Toggle.svelte';
	import type { ModelOption } from '#lib/api/api_types.ts';
	import type {
		DiagramParameter,
		ParameterGroup,
		ParameterValue,
		ParameterValues
	} from '#lib/features/diagram_viewer/diagram_parameters.ts';
	import ParameterControl from './ParameterControl.svelte';

	type Props = {
		parameters: DiagramParameter[];
		parameter_values: ParameterValues;
		on_parameter_change: (name: string, value: ParameterValue) => void;
		is_step_by_step: boolean;
		on_step_by_step_change: (is_step_by_step: boolean) => void;
		model: string;
		model_options: ModelOption[];
		// What the director should know about the selected model, if anything.
		model_note: string | null;
		on_model_change: (model: string) => void;
		// Whether a generation is running, during which its settings cannot change.
		is_generating: boolean;
	};

	type TabId = 'parameters' | 'effects';

	let {
		parameters,
		parameter_values,
		on_parameter_change,
		is_step_by_step,
		on_step_by_step_change,
		model,
		model_options,
		model_note,
		on_model_change,
		is_generating
	}: Props = $props();

	const tabs = [
		{ id: 'parameters', label: 'Parameters' },
		{ id: 'effects', label: 'Effects' }
	] as const;

	// Groups shown under each tab, with the heading each group gets.
	const tab_groups: Record<TabId, { group: ParameterGroup; heading: string }[]> = {
		parameters: [
			{ group: 'general', heading: 'Structure' },
			{ group: 'copy', heading: 'Copy' }
		],
		effects: [
			{ group: 'styling', heading: 'Styling' },
			{ group: 'animation', heading: 'Animation' }
		]
	};

	let selected_tab: TabId = $state('parameters');

	let sections = $derived(
		tab_groups[selected_tab]
			.map(({ group, heading }) => ({
				heading,
				parameters: parameters.filter((parameter) => parameter.group === group)
			}))
			.filter((section) => section.parameters.length > 0)
	);
</script>

<aside class="controls_panel" aria-label="Controls">
	<!-- Settings that apply to every generation, whatever the diagram exposes. -->
	<fieldset class="prompting" disabled={is_generating}>
		<legend class="heading">Prompting</legend>
		<Toggle
			label="Draw step by step"
			checked={is_step_by_step}
			on_change={on_step_by_step_change}
		/>
		<SelectField
			label="Model"
			value={model}
			options={model_options.map((option) => ({ value: option.id, label: option.label }))}
			on_change={on_model_change}
		/>
		{#if model_note}
			<p class="model_note">{model_note}</p>
		{/if}
	</fieldset>

	<Tabs
		{tabs}
		selected={selected_tab}
		label="Parameter groups"
		on_select={(id: TabId) => (selected_tab = id)}
	/>

	<!-- Show the selected tab's parameters, grouped the way the diagram declared them. -->
	<div class="sections" role="tabpanel">
		{#each sections as section (section.heading)}
			<section class="section">
				<h3 class="heading">{section.heading}</h3>
				{#each section.parameters as parameter (parameter.name)}
					<ParameterControl
						{parameter}
						value={parameter_values[parameter.name]}
						on_change={(value: ParameterValue) => on_parameter_change(parameter.name, value)}
					/>
				{/each}
			</section>
		{:else}
			<p class="empty">
				{#if parameters.length === 0}
					The diagram's exposed parameters appear here once it is drawn.
				{:else if selected_tab === 'effects'}
					This diagram exposes no styling or animation parameters.
				{:else}
					This diagram exposes no structure or copy parameters.
				{/if}
			</p>
		{/each}
	</div>
</aside>

<style>
	.controls_panel {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		min-height: 0;
		padding: 1rem;
		background: var(--color-panel);
	}

	.prompting {
		display: grid;
		gap: 0.75rem;
		margin: 0;
		padding: 0 0 1rem;
		border: 0;
		border-bottom: 1px solid var(--color-rule);
	}

	.model_note {
		margin: 0;
		color: var(--color-marker);
		font-size: 0.8125rem;
	}

	.heading {
		margin: 0;
		padding: 0;
		font-size: 0.875rem;
		font-weight: 700;
		font-stretch: 92%;
	}

	.sections {
		display: grid;
		align-content: start;
		gap: 1.25rem;
		min-height: 0;
		overflow-y: auto;
	}

	.section {
		display: grid;
		gap: 0.75rem;
	}

	.empty {
		margin: 0;
		color: var(--color-graphite);
	}
</style>
