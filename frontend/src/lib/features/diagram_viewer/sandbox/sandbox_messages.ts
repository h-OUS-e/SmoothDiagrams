/* Messages exchanged between the app and the sandboxed iframe. */

import type { ParameterValues } from '../diagram_parameters.ts';

export type RenderFailureStage = 'load' | 'render' | 'runtime';

export type AppToSandboxMessage =
	| { type: 'render'; render_id: number; code: string; values: ParameterValues; time: number }
	| { type: 'set_values'; values: ParameterValues }
	| { type: 'set_time'; time: number }
	| { type: 'capture'; capture_id: number };

export type SandboxToAppMessage =
	| { type: 'ready' }
	| { type: 'rendered'; render_id: number; svg_markup: string }
	| { type: 'failed'; render_id: number; stage: RenderFailureStage; message: string }
	| { type: 'captured'; capture_id: number; svg_markup: string | null };
