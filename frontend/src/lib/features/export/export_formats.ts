/* The formats a node can be exported in, and what each one is called. */

import type { ExportFormat } from '#lib/api/api_types.ts';

type FormatDetail = {
	label: string;
	file_extension: string;
	media_type: string;
	// Whether the file is made of pixels and so needs a size.
	has_pixels: boolean;
};

export const format_details: Record<ExportFormat, FormatDetail> = {
	svelte: {
		label: 'Svelte component',
		file_extension: '.svelte',
		media_type: 'text/plain',
		has_pixels: false
	},
	svg: { label: 'SVG', file_extension: '.svg', media_type: 'image/svg+xml', has_pixels: false },
	png: { label: 'PNG', file_extension: '.png', media_type: 'image/png', has_pixels: true },
	jpeg: { label: 'JPEG', file_extension: '.jpg', media_type: 'image/jpeg', has_pixels: true }
};

// Every format, in the order the director is offered them.
export const export_formats = Object.keys(format_details) as ExportFormat[];

// Longest side an exported image may have, in pixels; keep in step with the server's limit.
export const pixel_size_limit = 16384;
