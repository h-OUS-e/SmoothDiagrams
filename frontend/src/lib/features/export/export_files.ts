/* Make the file of an export in the browser and hand it to the director. */

import type { ExportFormat } from '#lib/api/api_types.ts';
import { replace_prop_defaults_in_worker } from '#lib/features/diagram_viewer/compiler/compile_client.ts';
import type { ParameterValues } from '#lib/features/diagram_viewer/diagram_parameters.ts';
import {
	read_view_box_size,
	type DiagramSize
} from '#lib/features/diagram_viewer/viewer_outcome.ts';
import { format_details } from './export_formats.ts';

// What the director chooses for an export.
export type ExportSettings = {
	format: ExportFormat;
	// What the director calls the file, without an extension.
	name: string;
	// Width of a PNG or JPEG in pixels; its height follows the diagram's proportions.
	pixel_width: number;
};

export type ExportRequest = ExportSettings & {
	source: string;
	values: ParameterValues;
	// Return the markup of the diagram as the viewer shows it right now.
	capture: () => Promise<string | null>;
};

export type ExportFile = {
	blob: Blob;
	file_name: string;
	// Size of a PNG or JPEG in pixels; null for the formats that have no fixed size.
	pixel_size: DiagramSize | null;
};

// Quality of a JPEG, from 0 to 1.
const jpeg_quality = 0.92;

// Color painted under a JPEG, which cannot be transparent.
const jpeg_background = '#ffffff';

// Milliseconds a downloaded file's address stays valid, which is long enough for the save to start.
const download_url_lifetime = 40_000;

/* ------------------------------------------------------------------ */
/* File names                                                          */
/* ------------------------------------------------------------------ */

// Return a file name for an export: a component name for Svelte, lower case words otherwise.
export function build_file_name(name: string, format: ExportFormat): string {
	const words = name.match(/[\p{L}\p{N}]+/gu) ?? [];
	const { file_extension } = format_details[format];

	// Name a component the way Svelte components are named, starting with a letter.
	if (format === 'svelte') {
		const component_name = words.map((word) => word[0].toUpperCase() + word.slice(1)).join('');
		const starts_with_letter = /^\p{L}/u.test(component_name);
		return `${starts_with_letter ? component_name : `Diagram${component_name}`}${file_extension}`;
	}
	return `${words.join('_').toLowerCase() || 'diagram'}${file_extension}`;
}

/* ------------------------------------------------------------------ */
/* Markup and pixels                                                   */
/* ------------------------------------------------------------------ */

// Return the height in pixels that keeps a diagram's proportions at a width.
export function scale_height(size: DiagramSize, pixel_width: number): number {
	return Math.max(1, Math.round((pixel_width * size.height) / size.width));
}

// Return markup whose root states a size, so it opens and draws at that size everywhere.
function set_svg_size(svg_markup: string, size: DiagramSize): string {
	// Parsing markup this way builds an inert document, so nothing inside it runs.
	const parsed = new DOMParser().parseFromString(svg_markup, 'image/svg+xml');
	if (parsed.querySelector('parsererror')) {
		throw new Error('The diagram on screen could not be read as SVG.');
	}

	parsed.documentElement.setAttribute('width', String(size.width));
	parsed.documentElement.setAttribute('height', String(size.height));
	return new XMLSerializer().serializeToString(parsed.documentElement);
}

// Return the diagram drawn into an image of a format made of pixels.
async function draw_image(
	svg_markup: string,
	pixel_size: DiagramSize,
	format: ExportFormat
): Promise<Blob> {
	// Load the markup as an image, which keeps any script inside it from running.
	const markup_url = URL.createObjectURL(
		new Blob([set_svg_size(svg_markup, pixel_size)], { type: format_details.svg.media_type })
	);
	const image = new Image();
	try {
		image.src = markup_url;
		await image.decode();
	} catch {
		throw new Error('The browser could not draw the diagram as an image.');
	} finally {
		URL.revokeObjectURL(markup_url);
	}

	// Draw it at the size asked for, over a background when the format has no transparency.
	const canvas = document.createElement('canvas');
	canvas.width = pixel_size.width;
	canvas.height = pixel_size.height;
	const context = canvas.getContext('2d');
	if (!context) throw new Error('The browser could not make an image this large.');
	if (format === 'jpeg') {
		context.fillStyle = jpeg_background;
		context.fillRect(0, 0, canvas.width, canvas.height);
	}
	context.drawImage(image, 0, 0, canvas.width, canvas.height);

	return new Promise((resolve, reject) => {
		canvas.toBlob(
			(blob) =>
				blob ? resolve(blob) : reject(new Error('The browser could not make an image this large.')),
			format_details[format].media_type,
			jpeg_quality
		);
	});
}

/* ------------------------------------------------------------------ */
/* Entry points                                                        */
/* ------------------------------------------------------------------ */

/**
 * Make the file of an export.
 *
 * A Svelte component is the step's source with the director's values written in as its
 * defaults. Every other format is the diagram as the viewer shows it at this moment.
 *
 * Args:
 *   request: What to export, in which format, and how to reach the viewer.
 *
 * Returns:
 *   The file's content, its name, and its size in pixels when it has one.
 *
 * Throws:
 *   Error: The viewer shows no diagram, or the browser could not make the file.
 */
export async function build_export_file(request: ExportRequest): Promise<ExportFile> {
	const { format } = request;
	const file_name = build_file_name(request.name, format);
	const media_type = format_details[format].media_type;

	if (format === 'svelte') {
		const outcome = await replace_prop_defaults_in_worker(request.source, request.values);
		if (!outcome.ok) throw new Error(outcome.message);
		return { blob: new Blob([outcome.source], { type: media_type }), file_name, pixel_size: null };
	}

	// Take the diagram as it looks now, with the director's values and the animation clock applied.
	const svg_markup = await request.capture();
	const view_box_size = svg_markup === null ? null : read_view_box_size(svg_markup);
	if (svg_markup === null || view_box_size === null) {
		throw new Error('There is no diagram on screen to export.');
	}

	if (format === 'svg') {
		const sized_markup = set_svg_size(svg_markup, view_box_size);
		return { blob: new Blob([sized_markup], { type: media_type }), file_name, pixel_size: null };
	}

	const pixel_size = {
		width: request.pixel_width,
		height: scale_height(view_box_size, request.pixel_width)
	};
	return { blob: await draw_image(svg_markup, pixel_size, format), file_name, pixel_size };
}

// Save a file to the director's computer through the browser's own download.
export function download_file(file: ExportFile) {
	const file_url = URL.createObjectURL(file.blob);
	const link = document.createElement('a');
	link.href = file_url;
	link.download = file.file_name;
	document.body.append(link);
	link.click();
	link.remove();

	// Release the address once the browser has had time to start saving.
	setTimeout(() => URL.revokeObjectURL(file_url), download_url_lifetime);
}
