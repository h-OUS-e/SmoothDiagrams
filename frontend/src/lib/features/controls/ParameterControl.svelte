<script lang="ts">
	import ColorField from '#lib/components/ui/ColorField.svelte';
	import SelectField from '#lib/components/ui/SelectField.svelte';
	import Slider from '#lib/components/ui/Slider.svelte';
	import TextField from '#lib/components/ui/TextField.svelte';
	import Toggle from '#lib/components/ui/Toggle.svelte';
	import type {
		DiagramParameter,
		ParameterValue
	} from '#lib/features/diagram_viewer/diagram_parameters.ts';

	type Props = {
		parameter: DiagramParameter;
		// Value the director chose, or undefined while the parameter is at its default.
		value: ParameterValue | undefined;
		on_change: (value: ParameterValue) => void;
		// Called once the director settles on a value, so a whole drag or typing counts as one change.
		on_change_ended: () => void;
	};

	let { parameter, value, on_change, on_change_ended }: Props = $props();

	// Change and end the change at once, for controls whose every change is already final.
	function change_and_end(next_value: ParameterValue) {
		on_change(next_value);
		on_change_ended();
	}
</script>

<!-- Show the control that fits the parameter's kind, falling back to its default value. -->
{#if parameter.kind === 'number'}
	<Slider
		label={parameter.label}
		value={typeof value === 'number' ? value : parameter.value}
		min={parameter.min}
		max={parameter.max}
		step={parameter.step}
		{on_change}
		{on_change_ended}
	/>
{:else if parameter.kind === 'color'}
	<ColorField
		label={parameter.label}
		value={typeof value === 'string' ? value : parameter.value}
		{on_change}
		{on_change_ended}
	/>
{:else if parameter.kind === 'text'}
	<TextField
		label={parameter.label}
		value={typeof value === 'string' ? value : parameter.value}
		{on_change}
		{on_change_ended}
	/>
{:else if parameter.kind === 'boolean'}
	<Toggle
		label={parameter.label}
		checked={typeof value === 'boolean' ? value : parameter.value}
		on_change={change_and_end}
	/>
{:else}
	<SelectField
		label={parameter.label}
		value={typeof value === 'string' ? value : parameter.value}
		options={parameter.options.map((option) => ({ value: option, label: option }))}
		on_change={change_and_end}
	/>
{/if}
