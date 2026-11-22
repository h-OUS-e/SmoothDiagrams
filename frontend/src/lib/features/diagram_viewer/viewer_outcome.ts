/* Result of the viewer trying to show one diagram source. */

import type { DiagramAnimation, DiagramParameter } from './diagram_parameters.ts';
import type { RenderFailureStage } from './sandbox/sandbox_messages.ts';

export type ViewerFailureStage = 'compile' | RenderFailureStage;

export type ViewerOutcome =
	| {
			ok: true;
			source: string;
			svg_markup: string;
			parameters: DiagramParameter[];
			animation: DiagramAnimation | null;
	  }
	| { ok: false; source: string; stage: ViewerFailureStage; message: string };

// What a viewer exposes to the component that holds a reference to it.
export type ViewerExports = {
	// Return the markup of the diagram as it looks right now, or null when none is shown.
	capture: () => Promise<string | null>;
};

// Return the width divided by the height of rendered markup, read from its viewBox.
export function read_aspect_ratio(svg_markup: string): number | null {
	const view_box = /<svg\b[^>]*\bviewBox="([^"]+)"/.exec(svg_markup)?.[1];
	if (!view_box) return null;

	const [, , width, height] = view_box
		.trim()
		.split(/[\s,]+/)
		.map(Number);
	return width > 0 && height > 0 ? width / height : null;
}
