import {
	get_interface,
	get_model_catalog,
	get_node,
	get_piece,
	get_project,
	list_library,
	list_priors,
	list_taste_priors
} from '#lib/api/api_client.ts';
import { load_from_server } from '#lib/api/load_errors.ts';
import type { PageLoad } from './$types';

// Name of the query parameter that remembers the open piece.
const piece_parameter = 'piece';

export const load: PageLoad = ({ params, url, fetch }) =>
	load_from_server(async () => {
		const [project, model_catalog, interface_state, library, priors, taste_priors] =
			await Promise.all([
				get_project(params.project_id, fetch),
				get_model_catalog(fetch),
				get_interface(params.project_id, fetch),
				list_library({ sort: 'date' }, fetch),
				list_priors(params.project_id, fetch),
				list_taste_priors(fetch)
			]);

		// Open the piece named in the address, or the project's first one.
		const piece_id = url.searchParams.get(piece_parameter);
		const piece_summary =
			project.pieces.find((piece) => piece.id === piece_id) ?? project.pieces.at(0);
		const piece = piece_summary ? await get_piece(piece_summary.id, fetch) : null;

		// Select the piece's newest node.
		const newest_node = piece?.nodes.at(-1);
		const node = newest_node ? await get_node(newest_node.id, fetch) : null;

		return {
			project,
			piece,
			node,
			model_catalog,
			interface_state,
			library,
			priors,
			taste_priors,
			piece_parameter
		};
	});
