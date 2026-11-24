/* Size of a resizable panel, kept in this browser so a reload keeps it. */

// Prefix of the storage keys, so they cannot collide with another app on the same host.
const storage_prefix = 'smooth-diagrams:panel-size:';

export class PanelSize {
	readonly default_size: number;
	readonly min_size: number;
	readonly max_size: number;
	#storage_key: string;
	#size: number = $state(0);

	/**
	 * Read the stored size of a panel, or start from its default.
	 *
	 * Args:
	 *   name: Name of the panel, unique among the panels that store a size.
	 *   default_size: Size in pixels before the viewer resizes the panel.
	 *   min_size: Smallest size in pixels the panel can be given.
	 *   max_size: Largest size in pixels the panel can be given.
	 */
	constructor(name: string, default_size: number, min_size: number, max_size: number) {
		this.default_size = default_size;
		this.min_size = min_size;
		this.max_size = max_size;
		this.#storage_key = storage_prefix + name;
		this.#size = this.#clamp(read_stored_number(this.#storage_key) ?? default_size);
	}

	get size(): number {
		return this.#size;
	}

	// Change the size within its bounds and store it for the next visit.
	set size(size: number) {
		this.#size = this.#clamp(size);
		write_stored_number(this.#storage_key, this.#size);
	}

	// Return the size moved inside the bounds, which also discards a stored value from older bounds.
	#clamp(size: number): number {
		return Math.min(this.max_size, Math.max(this.min_size, size));
	}
}

// Return the number stored under a key, or null when there is none or storage is blocked.
function read_stored_number(key: string): number | null {
	try {
		const stored = localStorage.getItem(key);
		const value = stored === null ? NaN : Number(stored);
		return Number.isFinite(value) ? value : null;
	} catch {
		return null;
	}
}

// Store a number under a key, and skip it silently when storage is blocked.
function write_stored_number(key: string, value: number) {
	try {
		localStorage.setItem(key, String(value));
	} catch {
		// Keep the size for this visit only; a private window can refuse storage.
	}
}
