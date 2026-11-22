<script lang="ts">
	import IconFrame from './IconFrame.svelte';

	type Props = {
		size?: number;
	};

	let { size }: Props = $props();
</script>

<IconFrame paths={['M3 13V8a3 3 0 0 1 3-3h7', 'M10 2l3 3-3 3']} {size} />
