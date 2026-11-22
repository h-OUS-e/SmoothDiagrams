/* Build the HTML document loaded into the viewer's sandboxed iframe. */

import { bootstrap_file_name, sandbox_modules, sandbox_runtime_path } from './sandbox_modules.ts';
import { base_style_attribute } from './serialize_svg.ts';

// Escape text for use inside a double-quoted HTML attribute.
function escape_attribute(text: string): string {
	return text.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
}

/**
 * Return the iframe document that loads the sandbox runtime and nothing else.
 *
 * Args:
 *   app_origin: Origin of the app, which serves the sandbox runtime files.
 *   nonce: Random value that lets the import map pass the content security policy.
 *
 * Returns:
 *   HTML for the iframe's srcdoc attribute.
 */
export function build_sandbox_document(app_origin: string, nonce: string): string {
	const runtime_url = `${app_origin}${sandbox_runtime_path}/`;

	// Map each allowed module to its runtime file, so every other import fails to resolve.
	const import_map = {
		imports: Object.fromEntries(
			sandbox_modules.map((module) => [module.specifier, `${runtime_url}${module.file_name}`])
		)
	};

	// Allow scripts only from the runtime and from blobs, and block every network request.
	const content_security_policy = [
		"default-src 'none'",
		`script-src 'nonce-${nonce}' ${runtime_url} blob:`,
		"style-src 'unsafe-inline'",
		'img-src data: blob:',
		'font-src data:',
		'media-src data: blob:'
	].join('; ');

	return `<!doctype html>
<html>
	<head>
		<meta charset="utf-8" />
		<meta http-equiv="Content-Security-Policy" content="${escape_attribute(content_security_policy)}" />
		<script type="importmap" nonce="${escape_attribute(nonce)}">${JSON.stringify(import_map)}</script>
		<style ${base_style_attribute}>
			html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: transparent; }
			body > svg { display: block; width: 100%; height: 100%; }
		</style>
	</head>
	<body>
		<script type="module" src="${escape_attribute(runtime_url + bootstrap_file_name)}"></script>
	</body>
</html>`;
}
