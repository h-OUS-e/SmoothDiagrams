<script lang="ts">
	import type { PromptControl } from '#lib/api/api_types.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import NumberField from '#lib/components/ui/NumberField.svelte';
	import TextAreaField from '#lib/components/ui/TextAreaField.svelte';
	import TextField from '#lib/components/ui/TextField.svelte';
	import { parse_options, prompt_control_kinds } from './prompt_controls.ts';

	type Props = {
		control: PromptControl;
		on_change: (changes: Partial<PromptControl>) => void;
		on_remove: () => void;
	};

	let { control, on_change, on_remove }: Props = $props();

	let kind_label = $derived(
		prompt_control_kinds.find((kind) => kind.value === control.kind)?.label ?? control.kind
	);

	// Change a slider's range, moving its value back inside when the range leaves it behind.
	function change_range(changes: { min?: number; max?: number; step?: number }) {
		const min = changes.min ?? control.min ?? 0;
		const max = changes.max ?? control.max ?? 100;
		const value = Math.min(Math.max(Number(control.value), min), max);
		on_change({ ...changes, value });
	}

	// Change a select's options, falling back to the first when the chosen one is gone.
	function change_options(text: string) {
		const options = parse_options(text);
		if (options.length === 0) return;

		const value = options.includes(String(control.value)) ? control.value : options[0];
		on_change({ options, value });
	}
</script>

<details class="prompt_control_editor">
	<summary>{control.label} <span class="kind">{kind_label}</span></summary>

	<!-- Let the director reword the control and what it tells the model. -->
	<div class="fields">
		<TextField
			label="Label"
			value={control.label}
			on_change={(label: string) => label.trim() !== '' && on_change({ label })}
		/>
		<TextAreaField
			label={'Instruction, with {value} where the value goes'}
			value={control.instruction}
			rows={3}
			on_change={(instruction: string) => instruction.trim() !== '' && on_change({ instruction })}
		/>

		{#if control.kind === 'slider'}
			<div class="range">
				<NumberField
					label="From"
					value={control.min ?? 0}
					on_change={(min: number) => change_range({ min })}
				/>
				<NumberField
					label="To"
					value={control.max ?? 100}
					on_change={(max: number) => change_range({ max })}
				/>
				<NumberField
					label="Step"
					value={control.step ?? 1}
					on_change={(step: number) => change_range({ step })}
				/>
			</div>
		{:else if control.kind === 'select'}
			<TextField
				label="Choices, separated by commas"
				value={(control.options ?? []).join(', ')}
				on_change={change_options}
			/>
		{/if}

		<Button variant="marker" onclick={on_remove}>Remove this control</Button>
	</div>
</details>

<style>
	.prompt_control_editor > summary {
		font-weight: 600;
		cursor: pointer;
	}

	.kind {
		color: var(--color-graphite);
		font-weight: 400;
	}

	.fields {
		display: grid;
		gap: 0.5rem;
		justify-items: start;
		padding: 0.5rem 0 0.25rem;
	}

	.fields > :global(label) {
		width: 100%;
	}

	.range {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.5rem;
		width: 100%;
	}
</style>
