<script lang="ts">
	import IconFrame from './IconFrame.svelte';

	type Props = {
		size?: number;
	};

	let { size }: Props = $props();
</script>

<IconFrame
	paths={['M2.5 6.5c2-2 3.5-2 5.5 0s3.5 2 5.5 0', 'M2.5 10.5c2-2 3.5-2 5.5 0s3.5 2 5.5 0']}
	{size}
/>
