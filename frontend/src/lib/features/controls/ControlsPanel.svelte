<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { ModelOption } from '#lib/api/api_types.ts';
	import PanelSection from '#lib/components/ui/PanelSection.svelte';
	import Tabs from '#lib/components/ui/Tabs.svelte';
	import type {
		DiagramParameter,
		ParameterGroup,
		ParameterValue,
		ParameterValues
	} from '#lib/features/diagram_viewer/diagram_parameters.ts';
	import InterfaceEditor from '#lib/features/interface/InterfaceEditor.svelte';
	import type { ProjectInterface } from '#lib/features/interface/project_interface.svelte.ts';
	import PromptingControls from '#lib/features/interface/PromptingControls.svelte';
	import ParameterControl from './ParameterControl.svelte';

	type Props = {
		parameters: DiagramParameter[];
		parameter_values: ParameterValues;
		on_parameter_change: (name: string, value: ParameterValue) => void;
		project_interface: ProjectInterface;
		model_options: ModelOption[];
		// Whether a generation is running, during which its settings cannot change.
		is_generating: boolean;
		// What the Export tab shows, which belongs to the diagram on screen and not to the controls.
		export_tab: Snippet;
	};

	type TabId = 'parameters' | 'effects' | 'interface' | 'export';
	type ParameterTabId = 'parameters' | 'effects';

	let {
		parameters,
		parameter_values,
		on_parameter_change,
		project_interface,
		model_options,
		is_generating,
		export_tab
	}: Props = $props();

	const tabs = [
		{ id: 'parameters', label: 'Parameters' },
		{ id: 'effects', label: 'Effects' },
		{ id: 'interface', label: 'Interface' },
		{ id: 'export', label: 'Export' }
	] as const;

	// Groups shown under each parameter tab, with the heading each group gets.
	const tab_groups: Record<ParameterTabId, { group: ParameterGroup; heading: string }[]> = {
		parameters: [
			{ group: 'general', heading: 'Structure' },
			{ group: 'copy', heading: 'Copy' }
		],
		effects: [
			{ group: 'styling', heading: 'Styling' },
			{ group: 'animation', heading: 'Animation' }
		]
	};

	let selected_tab = $state<TabId>('parameters');

	let sections = $derived(
		selected_tab === 'interface' || selected_tab === 'export'
			? []
			: tab_groups[selected_tab]
					.map(({ group, heading }) => ({
						heading,
						parameters: parameters.filter((parameter) => parameter.group === group)
					}))
					.filter((section) => section.parameters.length > 0)
	);
</script>

<!-- Dark, so the controls stand apart from the desk the diagram is judged on. -->
<aside class="controls_panel" data-theme="dark" aria-label="Controls">
	<PromptingControls {project_interface} {model_options} {is_generating} />

	<Tabs
		{tabs}
		selected={selected_tab}
		label="Control groups"
		on_select={(id: TabId) => (selected_tab = id)}
	/>

	<div class="sections" role="tabpanel">
		{#if selected_tab === 'interface'}
			<InterfaceEditor {project_interface} {is_generating} />
		{:else if selected_tab === 'export'}
			{@render export_tab()}
		{:else}
			<!-- Show the selected tab's parameters, grouped the way the diagram declared them. -->
			{#each sections as section (section.heading)}
				<PanelSection heading={section.heading}>
					{#each section.parameters as parameter (parameter.name)}
						<ParameterControl
							{parameter}
							value={parameter_values[parameter.name]}
							on_change={(value: ParameterValue) => on_parameter_change(parameter.name, value)}
						/>
					{/each}
				</PanelSection>
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
		{/if}
	</div>
</aside>

<style>
	.controls_panel {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		min-height: 0;
		padding: 1rem;
		overflow-y: auto;
		background: var(--color-panel);
	}

	.sections {
		display: grid;
		align-content: start;
		gap: 1.5rem;
	}

	.empty {
		margin: 0;
		color: var(--color-graphite);
	}
</style>
