<script lang="ts">
	import type { ExportDetail, ExportFormat } from '#lib/api/api_types.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import NumberField from '#lib/components/ui/NumberField.svelte';
	import PanelSection from '#lib/components/ui/PanelSection.svelte';
	import SelectField from '#lib/components/ui/SelectField.svelte';
	import TextField from '#lib/components/ui/TextField.svelte';
	import type { DiagramSize } from '#lib/features/diagram_viewer/viewer_outcome.ts';
	import { build_file_name, scale_height, type ExportSettings } from './export_files.ts';
	import { export_formats, format_details, pixel_size_limit } from './export_formats.ts';

	type Props = {
		// Whether the viewer shows a step that can be exported.
		can_export: boolean;
		// Size of the diagram on screen in its own units, or null when there is none.
		diagram_size: DiagramSize | null;
		// Name the file gets unless the director writes another.
		default_name: string;
		// Exports of the selected node, oldest first.
		exports: ExportDetail[];
		// Make the file, save it, and remember the export; rejects when the file cannot be made.
		on_export: (settings: ExportSettings) => Promise<void>;
	};

	let { can_export, diagram_size, default_name, exports, on_export }: Props = $props();

	// How many pixels an image gets for each unit of the diagram, unless the director sets a width.
	const default_scale = 2;

	const format_options = export_formats.map((format) => ({
		value: format,
		label: format_details[format].label
	}));

	// What each format saves, in the director's words.
	const format_notes: Record<ExportFormat, string> = {
		svelte: 'The source of this step, with the values you set as its defaults.',
		svg: 'The diagram as it looks now, at the time on the play slider.',
		png: 'The diagram as it looks now. Areas it leaves unpainted stay transparent.',
		jpeg: 'The diagram as it looks now. Areas it leaves unpainted turn white.'
	};

	const date_format = new Intl.DateTimeFormat(undefined, {
		dateStyle: 'medium',
		timeStyle: 'short'
	});

	let format = $state<ExportFormat>('png');
	let is_exporting = $state(false);
	let error_message = $state<string | null>(null);

	// Follow the open piece and the diagram on screen until the director types a value.
	let name = $derived(default_name);
	let default_pixel_width = $derived(Math.round((diagram_size?.width ?? 0) * default_scale));
	let pixel_width = $derived(default_pixel_width);

	let has_pixels = $derived(format_details[format].has_pixels);
	let pixel_height = $derived(diagram_size ? scale_height(diagram_size, pixel_width) : 0);
	let size_problem = $derived.by(() => {
		if (!has_pixels || !diagram_size) return null;
		if (!Number.isInteger(pixel_width) || pixel_width < 1) {
			return 'The width must be a whole number of pixels.';
		}
		if (pixel_width > pixel_size_limit || pixel_height > pixel_size_limit) {
			return `An image can be at most ${pixel_size_limit} pixels on a side.`;
		}
		return null;
	});
	let newest_exports = $derived(exports.toReversed());

	// Return the format a select's value names, which is always one of the formats it offers.
	function read_format(value: string): ExportFormat {
		return export_formats.find((candidate) => candidate === value) ?? 'png';
	}

	// Return a line describing a past export: its format, and its size when it has one.
	function describe_export(node_export: ExportDetail): string {
		const label = format_details[node_export.format].label;
		if (node_export.pixel_width === null || node_export.pixel_height === null) return label;
		return `${label}, ${node_export.pixel_width} by ${node_export.pixel_height}`;
	}

	// Export with the settings on screen and show why when the file cannot be made.
	async function export_diagram() {
		is_exporting = true;
		error_message = null;
		try {
			await on_export({ format, name, pixel_width });
		} catch (error) {
			error_message = error instanceof Error ? error.message : String(error);
		} finally {
			is_exporting = false;
		}
	}
</script>

<div class="export_panel">
	{#if can_export}
		<div class="new_export">
			<PanelSection heading="File">
				<!-- Keep each field next to the line that explains it. -->
				<div class="described_field">
					<SelectField
						label="Format"
						value={format}
						options={format_options}
						on_change={(value: string) => (format = read_format(value))}
					/>
					<p class="note">{format_notes[format]}</p>
				</div>

				<TextField label="File name" value={name} on_change={(value: string) => (name = value)} />

				{#if has_pixels}
					<div class="described_field">
						<NumberField
							label="Width in pixels"
							value={pixel_width}
							on_change={(value: number) => (pixel_width = value)}
						/>
						{#if size_problem}
							<p class="problem" role="alert">{size_problem}</p>
						{/if}
					</div>
				{/if}
			</PanelSection>

			<!-- Say what will be saved, then offer to save it. -->
			<div class="action">
				{#if !size_problem}
					<p class="summary">
						Saves {build_file_name(name, format)}{has_pixels
							? `, ${pixel_width} by ${pixel_height} pixels`
							: ''}.
					</p>
				{/if}
				<Button
					variant="primary"
					disabled={is_exporting || size_problem !== null}
					onclick={export_diagram}
				>
					{is_exporting ? 'Exporting' : 'Export'}
				</Button>
				{#if error_message}
					<p class="problem" role="alert">{error_message}</p>
				{/if}
			</div>
		</div>
	{:else}
		<p class="note">Select a step that shows a diagram to export it.</p>
	{/if}

	<!-- List the exports of the selected node, newest first. -->
	{#if newest_exports.length > 0}
		<div class="past_exports">
			<PanelSection heading="Exports of this node">
				<ul class="exports">
					{#each newest_exports as node_export (node_export.id)}
						<li class="export">
							<span class="export_format">{describe_export(node_export)}</span>
							<span class="export_date">
								{date_format.format(new Date(node_export.created_at))}
							</span>
						</li>
					{/each}
				</ul>
			</PanelSection>
		</div>
	{/if}
</div>

<style>
	.export_panel {
		display: grid;
		gap: 1.5rem;
	}

	.new_export {
		display: grid;
		gap: 1rem;
	}

	.described_field {
		display: grid;
		gap: 0.375rem;
	}

	.action {
		display: grid;
		gap: 0.5rem;
	}

	.note {
		margin: 0;
		color: var(--color-graphite);
		font-size: 0.8125rem;
	}

	.summary {
		margin: 0;
		font-size: 0.8125rem;
		font-variant-numeric: tabular-nums;
		overflow-wrap: anywhere;
	}

	.problem {
		margin: 0;
		color: var(--color-marker);
		font-size: 0.8125rem;
	}

	.past_exports {
		padding-top: 1.5rem;
		border-top: 1px solid var(--color-rule);
	}

	.exports {
		display: grid;
		gap: 0.375rem;
		margin: 0;
		padding: 0;
		list-style: none;
		font-variant-numeric: tabular-nums;
	}

	.export {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: 0 0.5rem;
	}

	.export_format {
		font-weight: 600;
	}

	.export_date {
		color: var(--color-graphite);
		font-size: 0.8125rem;
	}
</style>
