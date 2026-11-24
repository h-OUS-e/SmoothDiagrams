/* Tell apart the elements that take typed text, where the browser's own editing belongs. */

// Input types the director types text into, as opposed to sliders, swatches, and switches.
const text_input_types = new Set(['text', 'search', 'email', 'url', 'tel', 'password', 'number']);

// Return whether the element takes typed text.
export function is_text_field(target: EventTarget | null): boolean {
	if (target instanceof HTMLTextAreaElement) return true;
	if (target instanceof HTMLInputElement) return text_input_types.has(target.type);
	return target instanceof HTMLElement && target.isContentEditable;
}
