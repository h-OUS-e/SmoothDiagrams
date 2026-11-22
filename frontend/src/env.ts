/* Environment variables the app reads. */

import { defineEnvVars } from '@sveltejs/kit/env';

const default_backend_url = 'http://localhost:8000';

export const variables = defineEnvVars({
	BACKEND_URL: {
		public: true,
		description: 'Address of the local server that stores projects and calls the models.',
		schema: (value) => value || default_backend_url
	}
});
