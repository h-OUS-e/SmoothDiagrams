<script lang="ts">
	import PauseIcon from '#lib/components/icons/PauseIcon.svelte';
	import PlayIcon from '#lib/components/icons/PlayIcon.svelte';
	import RedirectIcon from '#lib/components/icons/RedirectIcon.svelte';
	import RejectIcon from '#lib/components/icons/RejectIcon.svelte';
	import StopIcon from '#lib/components/icons/StopIcon.svelte';
	import Button from '#lib/components/ui/Button.svelte';

	type Props = {
		// What a new prompt starts from, in the director's words.
		starting_point: string;
		is_generating: boolean;
		is_paused: boolean;
		// Whether the node being generated has a step that can be rejected.
		can_reject: boolean;
		on_start: (prompt: string) => void;
		on_redirect: (prompt: string) => void;
		on_reject: (reason: string | null) => void;
		on_pause: () => void;
		on_resume: () => void;
		on_stop: () => void;
	};

	let {
		starting_point,
		is_generating,
		is_paused,
		can_reject,
		on_start,
		on_redirect,
		on_reject,
		on_pause,
		on_resume,
		on_stop
	}: Props = $props();

	let text = $state('');
	let trimmed_text = $derived(text.trim());

	// Send the text as a new prompt, or as a redirect while a generation runs.
	function submit() {
		if (trimmed_text === '') return;

		if (is_generating) {
			on_redirect(trimmed_text);
		} else {
			on_start(trimmed_text);
		}
		text = '';
	}

	// Reject the newest step, with the text as the reason when there is any.
	function reject() {
		on_reject(trimmed_text === '' ? null : trimmed_text);
		text = '';
	}

	// Submit on Enter; Shift and Enter still adds a line.
	function handle_keydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			submit();
		}
	}
</script>

<!-- Use the post method, because the router treats a get form as a navigation. -->
<form
	class="prompt_box"
	method="post"
	onsubmit={(event) => {
		event.preventDefault();
		submit();
	}}
>
	<label class="label" for="prompt_text">
		{is_generating ? 'Steer the drawing' : starting_point}
	</label>
	<textarea
		id="prompt_text"
		class="text"
		rows="3"
		placeholder={is_generating
			? 'Say where to go instead, or why you reject the newest step'
			: 'Describe what you want to see'}
		bind:value={text}
		onkeydown={handle_keydown}></textarea>

	<!-- Offer steering while a generation runs, and a single start action otherwise. -->
	<div class="actions">
		{#if is_generating}
			<Button variant="primary" type="submit" disabled={trimmed_text === ''}>
				<RedirectIcon size={14} />
				Redirect
			</Button>
			<Button variant="marker" disabled={!can_reject} onclick={reject}>
				<RejectIcon size={14} />
				Reject step
			</Button>
			{#if is_paused}
				<Button onclick={on_resume}>
					<PlayIcon size={12} />
					Resume
				</Button>
			{:else}
				<Button onclick={on_pause}>
					<PauseIcon size={12} />
					Pause
				</Button>
			{/if}
			<Button onclick={on_stop}>
				<StopIcon size={12} />
				Stop
			</Button>
		{:else}
			<Button variant="primary" type="submit" disabled={trimmed_text === ''}>Draw</Button>
		{/if}
	</div>
</form>

<style>
	.prompt_box {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		min-height: 0;
		padding: 1rem;
		background: var(--color-panel);
	}

	.label {
		font-size: 0.875rem;
		font-weight: 700;
		font-stretch: 92%;
	}

	.text {
		flex: 1;
		min-height: 3.5rem;
		padding: 0.5rem;
		border: 1px solid var(--color-rule);
		border-radius: 2px;
		background: var(--color-paper);
		color: var(--color-ink);
		font: inherit;
		resize: none;
	}

	.text::placeholder {
		color: var(--color-graphite);
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
	}
</style>
