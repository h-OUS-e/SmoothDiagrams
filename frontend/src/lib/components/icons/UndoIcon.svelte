<script lang="ts">
	import IconFrame from './IconFrame.svelte';

	type Props = {
		size?: number;
	};

	let { size }: Props = $props();
</script>

<IconFrame paths={['M6 3.5 3 6.5l3 3', 'M3 6.5h6.5a3.5 3.5 0 0 1 0 7H7']} {size} />
