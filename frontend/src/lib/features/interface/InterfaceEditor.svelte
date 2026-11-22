<script lang="ts">
	import type { PromptControl, PromptControlKind } from '#lib/api/api_types.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import SelectField from '#lib/components/ui/SelectField.svelte';
	import TextAreaField from '#lib/components/ui/TextAreaField.svelte';
	import TextField from '#lib/components/ui/TextField.svelte';
	import PromptControlEditor from './PromptControlEditor.svelte';
	import { build_prompt_control, prompt_control_kinds } from './prompt_controls.ts';
	import type { ProjectInterface } from './project_interface.svelte.ts';

	type Props = {
		project_interface: ProjectInterface;
		// Whether a generation is running, during which the interface cannot change.
		is_generating: boolean;
	};

	let { project_interface, is_generating }: Props = $props();

	let settings = $derived(project_interface.settings);

	let new_label = $state('');
	let new_kind: PromptControlKind = $state('slider');
	let new_instruction = $state('');
	let can_add = $derived(new_label.trim() !== '' && new_instruction.trim() !== '');

	const date_format = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' });

	// Add the control described in the form and clear the form for the next one.
	function add_control() {
		if (!can_add) return;

		const taken_ids = settings.prompt_controls.map((control) => control.id);
		project_interface.add_control(
			build_prompt_control(new_label.trim(), new_kind, new_instruction.trim(), taken_ids)
		);
		new_label = '';
		new_instruction = '';
	}

	// Return the kind a select's value names, which is always one of the kinds it offers.
	function read_kind(value: string): PromptControlKind {
		return prompt_control_kinds.find((kind) => kind.value === value)?.value ?? 'slider';
	}
</script>

<fieldset class="interface_editor" disabled={is_generating}>
	<legend class="sr-only">Interface</legend>

	<!-- Prompt text the director can rewrite for this project. -->
	<section class="section">
		<h3 class="heading">Prompt templates</h3>
		<TextAreaField
			label="Direction for every diagram of this project"
			value={settings.prompt_templates.direction}
			placeholder="The product, the audience, the aesthetic"
			rows={4}
			on_change={(text: string) => project_interface.change_template('direction', text)}
		/>
		<TextAreaField
			label="How to work step by step"
			value={settings.prompt_templates.step_by_step}
			rows={6}
			on_change={(text: string) => project_interface.change_template('step_by_step', text)}
		/>
		<TextAreaField
			label="How to work in one pass"
			value={settings.prompt_templates.single_pass}
			rows={4}
			on_change={(text: string) => project_interface.change_template('single_pass', text)}
		/>
	</section>

	<!-- The controls shown under Prompting, each with the instruction it gives the model. -->
	<section class="section">
		<h3 class="heading">Prompt controls</h3>
		{#each settings.prompt_controls as control (control.id)}
			<PromptControlEditor
				{control}
				on_change={(changes: Partial<PromptControl>) =>
					project_interface.change_control(control.id, changes)}
				on_remove={() => project_interface.remove_control(control.id)}
			/>
		{/each}

		<details class="add">
			<summary>Add a prompt control</summary>
			<!-- Use the post method, because the router treats a get form as a navigation. -->
			<form
				class="add_form"
				method="post"
				onsubmit={(event) => {
					event.preventDefault();
					add_control();
				}}
			>
				<TextField
					label="Label"
					value={new_label}
					on_change={(label: string) => (new_label = label)}
				/>
				<SelectField
					label="Kind"
					value={new_kind}
					options={prompt_control_kinds}
					on_change={(kind: string) => (new_kind = read_kind(kind))}
				/>
				<TextAreaField
					label={'Instruction, with {value} where the value goes'}
					value={new_instruction}
					placeholder={'Warmth is {value} out of 100.'}
					on_change={(instruction: string) => (new_instruction = instruction)}
				/>
				<Button type="submit" disabled={!can_add}>Add control</Button>
			</form>
		</details>
	</section>

	<!-- Every saved version; one that made nodes never changes and can be brought back. -->
	<section class="section">
		<h3 class="heading">Versions</h3>
		<ol class="versions">
			{#each project_interface.versions as version (version.id)}
				<li class="version">
					<span>
						<span class="version_name">Version {version.version_number}</span>
						<span class="version_details">
							{date_format.format(new Date(version.created_at))},
							{version.node_count}
							{version.node_count === 1 ? 'node' : 'nodes'}
						</span>
					</span>
					{#if version.is_current}
						<span class="current">In use</span>
					{:else}
						<Button onclick={() => project_interface.restore(version.id)}>Restore</Button>
					{/if}
				</li>
			{/each}
		</ol>
	</section>
</fieldset>

<style>
	.interface_editor {
		display: grid;
		gap: 1.5rem;
		min-width: 0;
		margin: 0;
		padding: 0;
		border: 0;
	}

	.section {
		display: grid;
		gap: 0.75rem;
	}

	.heading {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 700;
		font-stretch: 92%;
	}

	.add > summary {
		color: var(--color-graphite);
		font-weight: 600;
		font-stretch: 92%;
		cursor: pointer;
	}

	.add_form {
		display: grid;
		gap: 0.5rem;
		justify-items: start;
		padding-top: 0.5rem;
	}

	.add_form > :global(label) {
		width: 100%;
	}

	.versions {
		display: grid;
		gap: 0.5rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.version {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.version_name {
		display: block;
		font-weight: 600;
	}

	.version_details {
		color: var(--color-graphite);
		font-size: 0.8125rem;
	}

	.current {
		color: var(--color-marker);
		font-weight: 600;
		font-stretch: 92%;
	}
</style>
