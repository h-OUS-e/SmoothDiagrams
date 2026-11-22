<script lang="ts">
	import IconFrame from './IconFrame.svelte';

	type Props = {
		size?: number;
	};

	let { size }: Props = $props();
</script>

<IconFrame paths={['M4 2.5v11l9-5.5z']} is_filled {size} />
