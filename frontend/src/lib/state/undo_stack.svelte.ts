/* Undo and redo over saved states of one value, such as a node's parameter values. */

// Most states kept to undo to, so a long session does not grow without bound.
const default_limit = 100;

export class UndoStack<T> {
	// States before each recorded change, oldest first.
	#undo_states: T[] = $state.raw([]);
	// States left by each undo, the most recently undone last.
	#redo_states: T[] = $state.raw([]);
	#limit: number;

	can_undo = $derived(this.#undo_states.length > 0);
	can_redo = $derived(this.#redo_states.length > 0);

	constructor(limit = default_limit) {
		this.#limit = limit;
	}

	// Remember the state before a change, which forgets every state that could be redone.
	record(previous_state: T) {
		this.#undo_states = [...this.#undo_states, previous_state].slice(-this.#limit);
		this.#redo_states = [];
	}

	// Return the state to go back to and keep the current one for redo, or null when there is none.
	undo(current_state: T): T | null {
		if (this.#undo_states.length === 0) return null;

		const previous_state = this.#undo_states[this.#undo_states.length - 1];
		this.#undo_states = this.#undo_states.slice(0, -1);
		this.#redo_states = [...this.#redo_states, current_state];
		return previous_state;
	}

	// Return the state the last undo left and keep the current one for undo, or null when there is none.
	redo(current_state: T): T | null {
		if (this.#redo_states.length === 0) return null;

		const next_state = this.#redo_states[this.#redo_states.length - 1];
		this.#redo_states = this.#redo_states.slice(0, -1);
		this.#undo_states = [...this.#undo_states, current_state];
		return next_state;
	}

	// Forget every recorded state.
	clear() {
		this.#undo_states = [];
		this.#redo_states = [];
	}
}
