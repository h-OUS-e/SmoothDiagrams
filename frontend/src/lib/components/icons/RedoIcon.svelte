<script lang="ts">
	import IconFrame from './IconFrame.svelte';

	type Props = {
		size?: number;
	};

	let { size }: Props = $props();
</script>

<IconFrame paths={['M10 3.5l3 3-3 3', 'M13 6.5H6.5a3.5 3.5 0 0 0 0 7H9']} {size} />
