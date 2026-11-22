import { list_projects } from '#lib/api/api_client.ts';
import { load_from_server } from '#lib/api/load_errors.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch }) =>
	load_from_server(async () => ({ projects: await list_projects(fetch) }));
