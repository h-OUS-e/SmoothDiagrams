<script lang="ts">
	import IconFrame from './IconFrame.svelte';

	type Props = {
		size?: number;
	};

	let { size }: Props = $props();
</script>

<IconFrame paths={['M8 10V2.5', 'M5 5.5l3-3 3 3', 'M3 10v3h10v-3']} {size} />
