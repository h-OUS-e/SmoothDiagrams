<script lang="ts">
	import IconFrame from './IconFrame.svelte';

	type Props = {
		size?: number;
	};

	let { size }: Props = $props();
</script>

<IconFrame paths={['M4 4l8 8', 'M12 4l-8 8']} {size} />
