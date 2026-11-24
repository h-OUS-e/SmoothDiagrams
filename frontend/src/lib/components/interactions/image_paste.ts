/* Read images pasted from the clipboard. */

import { is_text_field } from './text_fields.ts';

/**
 * Return the image a paste carries, unless the paste is text meant for a text field.
 *
 * Args:
 *   event: The paste event.
 *   accepted_types: Media types of the images to take, such as "image/png".
 *
 * Returns:
 *   The first pasted image of an accepted type, or null when there is none.
 */
export function read_pasted_image(
	event: ClipboardEvent,
	accepted_types: readonly string[]
): File | null {
	const clipboard = event.clipboardData;
	if (!clipboard) return null;

	// Leave text pasted into a text field alone, even when an image comes with it.
	if (is_text_field(event.target) && clipboard.types.includes('text/plain')) return null;

	// Take the first image of an accepted type.
	return Array.from(clipboard.files).find((file) => accepted_types.includes(file.type)) ?? null;
}
