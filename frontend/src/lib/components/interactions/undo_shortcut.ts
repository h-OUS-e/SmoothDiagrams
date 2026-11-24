/* Read the keyboard shortcuts for undo and redo. */

import { is_text_field } from './text_fields.ts';

export type UndoCommand = 'undo' | 'redo';

/**
 * Return the command a key press asks for, unless a text field should undo its own typing.
 *
 * Ctrl+Z undoes, and Ctrl+Y or Ctrl+Shift+Z redoes; Cmd takes the place of Ctrl on macOS.
 *
 * Args:
 *   event: The keydown event.
 *
 * Returns:
 *   The undo command, or null when the key press is not one.
 */
export function read_undo_shortcut(event: KeyboardEvent): UndoCommand | null {
	if (!(event.ctrlKey || event.metaKey) || event.altKey) return null;

	// Leave typing in a text field to the browser's own undo.
	if (is_text_field(event.target)) return null;

	// Compare the key's character, so the shortcut follows the keyboard layout.
	const key = event.key.toLowerCase();
	if (key === 'z') return event.shiftKey ? 'redo' : 'undo';
	if (key === 'y' && !event.shiftKey) return 'redo';
	return null;
}
