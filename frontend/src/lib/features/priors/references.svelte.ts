/* State of what guides generation: the shared library, the project's priors, and the taste priors. */

import * as api from '#lib/api/api_client.ts';
import type {
	LibraryItemDetail,
	LibraryOrder,
	LibrarySort,
	PriorChanges,
	PriorDetail,
	TastePriorChanges,
	TastePriorDetail
} from '#lib/api/api_types.ts';

// Milliseconds to wait after the last keystroke before storing a text the director is typing.
const save_delay = 500;

// Milliseconds of sorting the library after which the wait is explained to the director.
const slow_sort_delay = 2000;

export class References {
	library: LibraryItemDetail[] = $state([]);
	library_order: LibraryOrder = $state.raw({ sort: 'date' });
	// Whether the library is being loaded in another order, and whether that is taking long.
	is_sorting_library = $state(false);
	is_library_sort_slow = $state(false);
	priors: PriorDetail[] = $state([]);
	taste_priors: TastePriorDetail[] = $state([]);
	error_message: string | null = $state(null);

	// Ids of the library items the project already uses as priors.
	used_item_ids: string[] = $derived(
		this.priors.flatMap((prior) => (prior.library_item ? [prior.library_item.id] : []))
	);

	#project_id: string;
	// The item the director last compared the library with, kept for the next similarity sort.
	#compared_item_id: string | null = null;
	#library_request_count = 0;
	// eslint-disable-next-line svelte/prefer-svelte-reactivity -- bookkeeping that is never rendered
	#save_timers = new Map<string, ReturnType<typeof setTimeout>>();

	constructor(
		project_id: string,
		library: LibraryItemDetail[],
		priors: PriorDetail[],
		taste_priors: TastePriorDetail[]
	) {
		this.#project_id = project_id;
		this.library = library;
		this.priors = priors;
		this.taste_priors = taste_priors;
	}

	/* ------------------------------------------------------------------ */
	/* Library                                                             */
	/* ------------------------------------------------------------------ */

	// Reload the library in another order; similarity compares with the item last compared with.
	async sort_library(sort: LibrarySort) {
		if (sort !== 'similarity') {
			await this.#order_library({ sort });
			return;
		}

		// Compare with the first item on screen when the director has not chosen one yet.
		const compared_item_id = this.#compared_item_id ?? this.library.at(0)?.id;
		if (compared_item_id) await this.compare_library(compared_item_id);
	}

	// Reload the library ordered by how much each item looks like one of them.
	async compare_library(item_id: string) {
		this.#compared_item_id = item_id;
		await this.#order_library({ sort: 'similarity', similar_to: item_id });
	}

	// Upload an image into the library.
	async add_library_image(file: File) {
		await this.#run(async () => {
			await api.add_library_image(file);
			await this.#reload_library();
		});
	}

	// Send a node to the library, where every project can use it as a prior.
	async add_library_node(node_id: string) {
		await this.#run(async () => {
			await api.add_library_node(node_id);
			await this.#reload_library();
		});
	}

	// Remove an item from the library, and with it the priors that point at it.
	async remove_library_item(item_id: string) {
		await this.#run(async () => {
			await api.remove_library_item(item_id);
			this.library = this.library.filter((item) => item.id !== item_id);
			this.priors = this.priors.filter((prior) => prior.library_item?.id !== item_id);

			// Fall back to the newest first when the item the others were compared with is gone.
			if (this.#compared_item_id === item_id) {
				this.#compared_item_id = null;
				if (this.library_order.sort === 'similarity') this.library_order = { sort: 'date' };
			}
		});
	}

	/* ------------------------------------------------------------------ */
	/* Priors                                                              */
	/* ------------------------------------------------------------------ */

	// Use a library item as a prior of the project, unless it already is one.
	async use_as_prior(library_item_id: string) {
		if (this.used_item_ids.includes(library_item_id)) return;

		await this.#run(async () => {
			this.priors.push(await api.add_library_prior(this.#project_id, library_item_id));
		});
	}

	// Upload an image into the library and use it as a prior of the project.
	async add_image_prior(file: File) {
		await this.#run(async () => {
			const item = await api.add_library_image(file);
			this.priors.push(await api.add_library_prior(this.#project_id, item.id));
			await this.#reload_library();
		});
	}

	// Add a prior made of text, such as a brief.
	async add_text_prior(name: string, text_content: string) {
		await this.#run(async () => {
			this.priors.push(await api.add_text_prior(this.#project_id, name, text_content));
		});
	}

	// Change a prior on screen at once and store the change, after a pause when it is typed text.
	change_prior(prior_id: string, changes: PriorChanges) {
		const prior = this.priors.find((candidate) => candidate.id === prior_id);
		if (!prior) return;

		Object.assign(prior, changes);
		const is_typed = changes.prior_note !== undefined || changes.text_content !== undefined;
		this.#save(`prior ${prior_id}`, is_typed, () => api.change_prior(prior_id, changes));
	}

	async remove_prior(prior_id: string) {
		await this.#run(async () => {
			await api.remove_prior(prior_id);
			this.priors = this.priors.filter((prior) => prior.id !== prior_id);
		});
	}

	/* ------------------------------------------------------------------ */
	/* Taste priors                                                        */
	/* ------------------------------------------------------------------ */

	// Add a taste prior made of text: taste notes, or a skill document.
	async add_text_taste_prior(kind: 'text' | 'skill', name: string, text_content: string) {
		await this.#run(async () => {
			this.taste_priors.push(await api.add_text_taste_prior(kind, name, text_content));
		});
	}

	async add_image_taste_prior(file: File) {
		await this.#run(async () => {
			this.taste_priors.push(await api.add_image_taste_prior(file));
		});
	}

	// Change a taste prior's name or text on screen at once and store the change.
	change_taste_prior(taste_prior_id: string, changes: TastePriorChanges) {
		const taste_prior = this.taste_priors.find((candidate) => candidate.id === taste_prior_id);
		if (!taste_prior) return;

		Object.assign(taste_prior, changes);
		this.#save(`taste prior ${taste_prior_id}`, changes.text_content !== undefined, () =>
			api.change_taste_prior(taste_prior_id, changes)
		);
	}

	async remove_taste_prior(taste_prior_id: string) {
		await this.#run(async () => {
			await api.remove_taste_prior(taste_prior_id);
			this.taste_priors = this.taste_priors.filter(
				(taste_prior) => taste_prior.id !== taste_prior_id
			);
		});
	}

	// Leave the page: drop the saves that are still waiting.
	dispose() {
		for (const timer of this.#save_timers.values()) clearTimeout(timer);
	}

	/* ------------------------------------------------------------------ */
	/* Helpers                                                             */
	/* ------------------------------------------------------------------ */

	// Load the library in an order and keep that order, unless a newer request overtook this one.
	async #order_library(order: LibraryOrder) {
		this.#library_request_count += 1;
		const request_number = this.#library_request_count;

		// Notice a load that takes long, which the first comparison does while the model downloads.
		this.is_sorting_library = true;
		const slow_timer = setTimeout(() => {
			if (request_number === this.#library_request_count) this.is_library_sort_slow = true;
		}, slow_sort_delay);

		await this.#run(async () => {
			const library = await api.list_library(order);
			if (request_number !== this.#library_request_count) return;
			this.library = library;
			this.library_order = order;
		});

		clearTimeout(slow_timer);
		if (request_number === this.#library_request_count) {
			this.is_sorting_library = false;
			this.is_library_sort_slow = false;
		}
	}

	// Load the library again in the order it is shown in.
	async #reload_library() {
		this.library = await api.list_library(this.library_order);
	}

	// Store a change now, or after typing has paused, replacing a waiting save of the same thing.
	#save(key: string, is_delayed: boolean, store: () => Promise<unknown>) {
		const waiting_timer = this.#save_timers.get(key);
		if (waiting_timer) clearTimeout(waiting_timer);

		const timer = setTimeout(
			() => {
				this.#save_timers.delete(key);
				void this.#run(async () => {
					await store();
				});
			},
			is_delayed ? save_delay : 0
		);
		this.#save_timers.set(key, timer);
	}

	// Run a request and show its error instead of throwing.
	async #run(work: () => Promise<void>) {
		try {
			this.error_message = null;
			await work();
		} catch (error) {
			this.error_message = error instanceof Error ? error.message : String(error);
		}
	}
}
