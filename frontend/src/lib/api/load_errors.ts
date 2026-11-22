/* Turn failed requests in load functions into errors the error page can explain. */

import { error } from '@sveltejs/kit';
import { ServerResponseError, ServerUnreachableError } from './api_client.ts';

// Status the error page recognizes as "the local server is not running".
export const server_unreachable_status = 503;

// Run the requests of a load function, mapping their failures to page errors.
export async function load_from_server<Result>(work: () => Promise<Result>): Promise<Result> {
	try {
		return await work();
	} catch (caught) {
		if (caught instanceof ServerUnreachableError) {
			error(server_unreachable_status, caught.message);
		}
		if (caught instanceof ServerResponseError) {
			error(caught.status, caught.message);
		}
		throw caught;
	}
}
