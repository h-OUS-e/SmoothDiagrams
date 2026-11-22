<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { create_project } from '#lib/api/api_client.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import SelectField from '#lib/components/ui/SelectField.svelte';
	import DiagramThumbnail from '#lib/features/diagram_viewer/DiagramThumbnail.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// Value of the choice that starts a project from the default interface.
	const default_interface = '';

	let project_name = $state('');
	let source_version_id = $state(default_interface);

	// Offer every interface version of every project as a starting point.
	let interface_options = $derived([
		{ value: default_interface, label: 'The default interface' },
		...data.interface_sources.map((source) => ({
			value: source.id,
			label: `${source.project_name}, version ${source.version_number}`
		}))
	]);
	let is_creating = $state(false);
	let error_message: string | null = $state(null);

	const date_format = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' });

	// Create a project from the typed name and open it.
	async function create_and_open_project() {
		const name = project_name.trim();
		if (name === '' || is_creating) return;

		is_creating = true;
		error_message = null;
		try {
			const project = await create_project(name, source_version_id || null);
			await goto(resolve('/projects/[project_id]', { project_id: project.id }));
		} catch (error) {
			error_message = error instanceof Error ? error.message : String(error);
		} finally {
			is_creating = false;
		}
	}
</script>

<svelte:head>
	<title>Projects - SmoothDiagrams</title>
</svelte:head>

<main class="home">
	<header class="header">
		<h1 class="title">Projects</h1>

		<!-- Use the post method, because the router treats a get form as a navigation. -->
		<form
			class="create"
			method="post"
			onsubmit={(event) => {
				event.preventDefault();
				void create_and_open_project();
			}}
		>
			<label class="sr-only" for="project_name">Name of the new project</label>
			<input
				id="project_name"
				class="name"
				type="text"
				placeholder="Name a new project"
				bind:value={project_name}
			/>
			<div class="source">
				<SelectField
					label="Start from the interface of"
					value={source_version_id}
					options={interface_options}
					on_change={(version_id: string) => (source_version_id = version_id)}
				/>
			</div>
			<Button variant="primary" type="submit" disabled={project_name.trim() === '' || is_creating}>
				Create project
			</Button>
		</form>
	</header>

	{#if error_message}
		<p class="error" role="alert">{error_message}</p>
	{/if}

	<!-- Show each project as the sheet of its newest diagram. -->
	<ul class="projects">
		{#each data.projects as project (project.id)}
			<li>
				<a class="project" href={resolve('/projects/[project_id]', { project_id: project.id })}>
					<span class="sheet">
						<DiagramThumbnail svg_markup={project.cover_svg} label="" />
					</span>
					<span class="project_name">{project.name}</span>
					<span class="details">
						{project.piece_count}
						{project.piece_count === 1 ? 'piece' : 'pieces'}, started
						{date_format.format(new Date(project.created_at))}
					</span>
				</a>
			</li>
		{:else}
			<li class="empty">No projects yet. Name one above to start drawing.</li>
		{/each}
	</ul>
</main>

<style>
	.home {
		max-width: 72rem;
		margin: 0 auto;
		padding: 2.5rem 1.5rem 4rem;
	}

	.header {
		display: flex;
		flex-wrap: wrap;
		align-items: end;
		justify-content: space-between;
		gap: 1rem 2rem;
		margin-bottom: 2rem;
	}

	.title {
		margin: 0;
		font-size: 2.75rem;
		font-weight: 800;
		font-stretch: 118%;
		line-height: 1;
		letter-spacing: -0.02em;
	}

	.create {
		display: flex;
		flex-wrap: wrap;
		align-items: end;
		gap: 0.375rem;
	}

	.source {
		width: 15rem;
	}

	.name {
		width: 16rem;
		max-width: 100%;
		min-height: 2rem;
		padding: 0 0.625rem;
		border: 1px solid var(--color-rule);
		border-radius: 3px;
		background: var(--color-paper);
		color: var(--color-ink);
		font: inherit;
	}

	.name::placeholder {
		color: var(--color-graphite);
	}

	.error {
		color: var(--color-marker);
	}

	.projects {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
		gap: 2rem 1.5rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.project {
		display: grid;
		gap: 0.125rem;
		color: inherit;
		text-decoration: none;
	}

	.sheet {
		display: block;
		aspect-ratio: 4 / 3;
		margin-bottom: 0.5rem;
		background: var(--color-paper);
		box-shadow:
			0 1px 0 var(--color-rule),
			0 14px 28px -20px rgb(27 29 33 / 0.5);
		transition: translate 160ms;
	}

	.project:hover .sheet {
		translate: 0 -3px;
	}

	.project_name {
		font-size: 1rem;
		font-weight: 700;
		font-stretch: 105%;
	}

	.details {
		color: var(--color-graphite);
	}

	.empty {
		grid-column: 1 / -1;
		color: var(--color-graphite);
		font-size: 1rem;
	}
</style>
