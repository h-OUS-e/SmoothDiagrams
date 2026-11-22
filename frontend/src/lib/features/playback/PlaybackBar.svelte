<script lang="ts">
	import PauseIcon from '#lib/components/icons/PauseIcon.svelte';
	import PlayIcon from '#lib/components/icons/PlayIcon.svelte';
	import type { DiagramAnimation } from '#lib/features/diagram_viewer/diagram_parameters.ts';

	type Props = {
		animation: DiagramAnimation;
		// Position of the animation clock, in seconds.
		time: number;
		on_time_change: (time: number) => void;
	};

	let { animation, time, on_time_change }: Props = $props();

	let is_playing = $state(false);

	// Start from the beginning when play is pressed at the end of an animation that does not loop.
	function toggle_playing() {
		if (!is_playing && time >= animation.duration) on_time_change(0);
		is_playing = !is_playing;
	}

	// Advance the clock on every animation frame while playing.
	$effect(() => {
		if (!is_playing) return;

		let last_frame_time = performance.now();
		let frame_id = requestAnimationFrame(function advance(frame_time) {
			const elapsed = (frame_time - last_frame_time) / 1000;
			last_frame_time = frame_time;

			// Wrap around when looping; otherwise stop at the end.
			let next_time = time + elapsed;
			if (next_time >= animation.duration) {
				if (animation.loop) {
					next_time %= animation.duration;
				} else {
					next_time = animation.duration;
					is_playing = false;
				}
			}
			on_time_change(next_time);
			frame_id = requestAnimationFrame(advance);
		});

		return () => cancelAnimationFrame(frame_id);
	});
</script>

<div class="playback_bar">
	<button
		class="play"
		type="button"
		aria-label={is_playing ? 'Pause the animation' : 'Play the animation'}
		onclick={toggle_playing}
	>
		{#if is_playing}
			<PauseIcon size={12} />
		{:else}
			<PlayIcon size={12} />
		{/if}
	</button>

	<input
		class="scrubber"
		type="range"
		aria-label="Animation time"
		min="0"
		max={animation.duration}
		step="0.01"
		value={time}
		oninput={(event) => on_time_change(event.currentTarget.valueAsNumber)}
	/>

	<span class="time">{time.toFixed(1)} / {animation.duration.toFixed(1)} s</span>
</div>

<style>
	.playback_bar {
		display: flex;
		align-items: center;
		gap: 0.625rem;
	}

	.play {
		display: grid;
		flex: none;
		place-items: center;
		width: 1.5rem;
		height: 1.5rem;
		padding: 0;
		border: 1px solid var(--color-ink);
		border-radius: 50%;
		background: none;
		color: var(--color-ink);
		cursor: pointer;
	}

	.scrubber {
		flex: 1;
		height: 1.25rem;
		margin: 0;
		appearance: none;
		background: transparent;
		cursor: pointer;
	}

	.scrubber::-webkit-slider-runnable-track {
		height: 2px;
		background: var(--color-graphite);
	}

	.scrubber::-moz-range-track {
		height: 2px;
		background: var(--color-graphite);
	}

	.scrubber::-webkit-slider-thumb {
		width: 0.75rem;
		height: 0.75rem;
		margin-top: calc(-0.375rem + 1px);
		appearance: none;
		border-radius: 50%;
		background: var(--color-ink);
	}

	.scrubber::-moz-range-thumb {
		width: 0.75rem;
		height: 0.75rem;
		border: 0;
		border-radius: 50%;
		background: var(--color-ink);
	}

	.time {
		flex: none;
		color: var(--color-graphite);
		font-size: 0.8125rem;
		font-variant-numeric: tabular-nums;
	}
</style>
