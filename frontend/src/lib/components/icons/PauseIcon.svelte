<script lang="ts">
	import IconFrame from './IconFrame.svelte';

	type Props = {
		size?: number;
	};

	let { size }: Props = $props();
</script>

<IconFrame paths={['M3.5 2.5h3v11h-3z', 'M9.5 2.5h3v11h-3z']} is_filled {size} />
