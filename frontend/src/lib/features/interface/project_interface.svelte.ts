/* State of a project's interface: the settings being edited and the versions saved so far. */

import * as api from '#lib/api/api_client.ts';
import type {
	InterfaceSettings,
	InterfaceState,
	InterfaceVersionSummary,
	PromptControl
} from '#lib/api/api_types.ts';

// Milliseconds to wait after the last change before storing the settings.
const save_delay = 600;

export class ProjectInterface {
	settings: InterfaceSettings = $state()!;
	version_number = $state(0);
	versions: InterfaceVersionSummary[] = $state.raw([]);
	error_message: string | null = $state(null);

	#project_id: string;
	#save_timer: ReturnType<typeof setTimeout> | null = null;
	#running_save: Promise<void> = Promise.resolve();
	// Whether the newest save reached the server; false after one failed.
	#is_stored = true;

	constructor(project_id: string, state: InterfaceState) {
		this.#project_id = project_id;
		this.settings = state.settings;
		this.#take_versions(state);
	}

	/* ------------------------------------------------------------------ */
	/* Changes                                                             */
	/* ------------------------------------------------------------------ */

	// Change some of the settings on screen at once and store them shortly after.
	change(changes: Partial<InterfaceSettings>) {
		Object.assign(this.settings, changes);
		this.#schedule_save();
	}

	// Change the wording of one prompt template.
	change_template(name: keyof InterfaceSettings['prompt_templates'], text: string) {
		this.settings.prompt_templates[name] = text;
		this.#schedule_save();
	}

	// Change the value or the definition of one prompt control.
	change_control(control_id: string, changes: Partial<PromptControl>) {
		const control = this.settings.prompt_controls.find((candidate) => candidate.id === control_id);
		if (!control) return;

		Object.assign(control, changes);
		this.#schedule_save();
	}

	add_control(control: PromptControl) {
		this.settings.prompt_controls.push(control);
		this.#schedule_save();
	}

	remove_control(control_id: string) {
		this.settings.prompt_controls = this.settings.prompt_controls.filter(
			(control) => control.id !== control_id
		);
		this.#schedule_save();
	}

	// Switch a taste prior on or off for this project.
	set_taste_prior_enabled(taste_prior_id: string, is_enabled: boolean) {
		const other_ids = this.settings.disabled_taste_prior_ids.filter((id) => id !== taste_prior_id);
		this.settings.disabled_taste_prior_ids = is_enabled
			? other_ids
			: [...other_ids, taste_prior_id];
		this.#schedule_save();
	}

	/* ------------------------------------------------------------------ */
	/* Versions                                                            */
	/* ------------------------------------------------------------------ */

	// Store pending changes now and return whether the server has the settings on screen.
	async flush(): Promise<boolean> {
		if (this.#save_timer) {
			clearTimeout(this.#save_timer);
			this.#save_timer = null;
			this.#start_save();
		}
		await this.#running_save;
		return this.#is_stored;
	}

	// Make an earlier version the current one again, replacing the settings on screen.
	async restore(interface_version_id: string) {
		await this.flush();
		await this.#run(async () => {
			const state = await api.restore_interface(this.#project_id, interface_version_id);
			this.settings = state.settings;
			this.#take_versions(state);
		});
	}

	// Reload the versions, whose node counts change when a generation uses one.
	async refresh_versions() {
		await this.#run(async () => {
			this.#take_versions(await api.get_interface(this.#project_id));
		});
	}

	// Leave the page: store what is still waiting, without holding the page up.
	dispose() {
		void this.flush();
	}

	/* ------------------------------------------------------------------ */
	/* Helpers                                                             */
	/* ------------------------------------------------------------------ */

	// Take the version details of a server answer, leaving the settings on screen alone.
	#take_versions(state: InterfaceState) {
		this.version_number = state.version_number;
		this.versions = state.versions;
	}

	// Store the settings after a pause, replacing a save that is still waiting.
	#schedule_save() {
		if (this.#save_timer) clearTimeout(this.#save_timer);
		this.#save_timer = setTimeout(() => {
			this.#save_timer = null;
			this.#start_save();
		}, save_delay);
	}

	// Store the settings as they are now, after any save that is still running.
	#start_save() {
		const settings = $state.snapshot(this.settings);
		this.#running_save = this.#running_save.then(async () => {
			this.#is_stored = await this.#run(async () => {
				this.#take_versions(await api.save_interface(this.#project_id, settings));
			});
		});
	}

	// Run a request, show its error instead of throwing, and return whether it succeeded.
	async #run(work: () => Promise<void>): Promise<boolean> {
		try {
			await work();
			this.error_message = null;
			return true;
		} catch (error) {
			this.error_message = error instanceof Error ? error.message : String(error);
			return false;
		}
	}
}
