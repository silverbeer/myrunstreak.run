<template>
  <img
    src="/logo.png"
    alt="MyRunStreak.run"
    :style="{ height: `${size}px` }"
    class="w-auto select-none"
    draggable="false"
  />
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 34 })
</script>
