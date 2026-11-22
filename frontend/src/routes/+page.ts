import { list_interface_sources, list_projects } from '#lib/api/api_client.ts';
import { load_from_server } from '#lib/api/load_errors.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch }) =>
	load_from_server(async () => {
		const [projects, interface_sources] = await Promise.all([
			list_projects(fetch),
			list_interface_sources(fetch)
		]);
		return { projects, interface_sources };
	});
