<script lang="ts">
	import type { PromptControl, PromptControlValue } from '#lib/api/api_types.ts';
	import SelectField from '#lib/components/ui/SelectField.svelte';
	import Slider from '#lib/components/ui/Slider.svelte';
	import TextField from '#lib/components/ui/TextField.svelte';
	import Toggle from '#lib/components/ui/Toggle.svelte';

	type Props = {
		control: PromptControl;
		on_change: (value: PromptControlValue) => void;
	};

	let { control, on_change }: Props = $props();
</script>

<!-- Show the field that fits the control's kind. -->
{#if control.kind === 'slider'}
	<Slider
		label={control.label}
		value={Number(control.value)}
		min={control.min ?? 0}
		max={control.max ?? 100}
		step={control.step ?? 1}
		{on_change}
	/>
{:else if control.kind === 'select'}
	<SelectField
		label={control.label}
		value={String(control.value)}
		options={(control.options ?? []).map((option) => ({ value: option, label: option }))}
		{on_change}
	/>
{:else if control.kind === 'toggle'}
	<Toggle label={control.label} checked={control.value === true} {on_change} />
{:else}
	<TextField label={control.label} value={String(control.value)} {on_change} />
{/if}
