/* Turn the mounted diagram into standalone SVG markup. Runs inside the sandbox. */

const svg_namespace = 'http://www.w3.org/2000/svg';

// Attribute marking the sandbox's own stylesheet, which must stay out of the markup.
export const base_style_attribute = 'data-sandbox-base';

// Return the text of every stylesheet the diagram injected into the document.
function collect_diagram_css(document: Document): string {
	const css_blocks: string[] = [];

	for (const style_sheet of document.styleSheets) {
		const owner = style_sheet.ownerNode;
		if (owner instanceof Element && owner.hasAttribute(base_style_attribute)) continue;

		for (const rule of style_sheet.cssRules) {
			css_blocks.push(rule.cssText);
		}
	}

	return css_blocks.join('\n');
}

// Return the diagram as SVG markup that renders the same outside the sandbox.
export function serialize_svg(svg: SVGSVGElement): string {
	// Copy the element so the mounted diagram stays untouched.
	const copy = svg.cloneNode(true) as SVGSVGElement;
	copy.setAttribute('xmlns', svg_namespace);

	// Carry the scoped styles along, because they live in the document head.
	const css_text = collect_diagram_css(svg.ownerDocument);
	if (css_text) {
		const style = svg.ownerDocument.createElementNS(svg_namespace, 'style');
		style.textContent = css_text;
		copy.prepend(style);
	}

	return new XMLSerializer().serializeToString(copy);
}
