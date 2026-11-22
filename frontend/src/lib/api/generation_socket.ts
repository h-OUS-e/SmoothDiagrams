/* One generation's WebSocket. Keep the messages in step with backend/smooth_diagrams/generation/messages.py. */

import { get_generations_url } from './api_client.ts';
import type { NodeDetail, NodeStatus, StepDetail } from './api_types.ts';

export type StartCommand = {
	type: 'start';
	piece_id: string;
	parent_step_id: string | null;
	// The uploaded node to continue from, which has no step to name.
	parent_node_id: string | null;
	prompt: string;
};

export type SteeringCommand =
	| {
			type: 'step_outcome';
			step_token: string;
			ok: boolean;
			render_svg: string | null;
			message: string | null;
	  }
	| { type: 'pause' }
	| { type: 'resume' }
	| { type: 'redirect'; prompt: string }
	| { type: 'reject_step'; reason: string | null }
	| { type: 'stop' };

export type GenerationEvent =
	| { type: 'node_created'; node: NodeDetail }
	| { type: 'reasoning_progress'; text: string }
	| { type: 'step_proposed'; step_token: string; source: string; step_reasoning: string }
	| { type: 'step_saved'; step: StepDetail }
	| { type: 'step_failed'; message: string }
	| { type: 'step_rejected'; step_id: string }
	| { type: 'paused' }
	| { type: 'resumed' }
	| { type: 'generation_ended'; status: NodeStatus; message: string | null };

export type GenerationSocket = {
	send: (command: SteeringCommand) => void;
	close: () => void;
};

/**
 * Open a socket, start a generation on it, and report what happens.
 *
 * Args:
 *   start: What to generate.
 *   on_event: Called for every event the server sends.
 *   on_closed: Called once when the socket closes, with whether the generation had ended first.
 *
 * Returns:
 *   Functions to steer the generation and to leave it.
 */
export function open_generation_socket(
	start: StartCommand,
	on_event: (event: GenerationEvent) => void,
	on_closed: (has_ended: boolean) => void
): GenerationSocket {
	const socket = new WebSocket(get_generations_url());
	let has_ended = false;

	socket.addEventListener('open', () => socket.send(JSON.stringify(start)));
	socket.addEventListener('message', (message: MessageEvent<string>) => {
		const event = JSON.parse(message.data) as GenerationEvent;
		if (event.type === 'generation_ended') has_ended = true;
		on_event(event);
	});
	socket.addEventListener('close', () => on_closed(has_ended));

	return {
		send(command) {
			if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(command));
		},
		close() {
			socket.close();
		}
	};
}
