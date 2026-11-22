/* Serve the built sandbox runtime to the viewer's iframe, which has an opaque origin. */

import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const runtime_directory = '/.sandbox_runtime';

// Load each built runtime file as text, on demand.
const runtime_files = import.meta.glob<string>('/.sandbox_runtime/*.js', {
	query: '?raw',
	import: 'default'
});

export const GET: RequestHandler = async ({ params }) => {
	const load_file = runtime_files[`${runtime_directory}/${params.file}`];
	if (!load_file) error(404, 'Unknown sandbox runtime file');

	// Allow any origin, because a sandboxed iframe has none and the runtime is public code.
	return new Response(await load_file(), {
		headers: {
			'content-type': 'text/javascript; charset=utf-8',
			'access-control-allow-origin': '*',
			'cache-control': 'no-cache'
		}
	});
};
