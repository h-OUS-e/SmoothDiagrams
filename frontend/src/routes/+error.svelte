<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { server_unreachable_status } from '#lib/api/load_errors.ts';

	// Run through uv, so the command works whichever Python environment is active.
	const start_command = 'uv run uvicorn smooth_diagrams.main:app --port 8000';
</script>

<main class="error_page">
	<!-- Say what went wrong and what to do about it. -->
	{#if page.status === server_unreachable_status}
		<h1 class="title">The local server is not running</h1>
		<p>
			Projects are stored by a small server on this computer, and the page could not reach it. Start
			it from the <code>backend</code> folder, then reload this page.
		</p>
		<pre class="command">{start_command}</pre>
	{:else}
		<h1 class="title">{page.status}: {page.error?.message}</h1>
		<p><a href={resolve('/')}>Go to your projects</a></p>
	{/if}
</main>

<style>
	.error_page {
		max-width: 38rem;
		margin: 0 auto;
		padding: 4rem 1.5rem;
		font-size: 1rem;
		line-height: 1.5;
	}

	.title {
		margin: 0 0 1rem;
		font-size: 1.75rem;
		font-weight: 750;
		font-stretch: 112%;
		line-height: 1.15;
	}

	.command {
		padding: 0.75rem 1rem;
		overflow-x: auto;
		background: var(--color-ink);
		color: var(--color-paper);
		font-size: 0.875rem;
	}
</style>
