<template>
  <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5 transition hover:shadow-md">
    <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide">
      {{ label }}
    </p>
    <p class="mt-2 text-3xl font-bold" :class="valueClass">
      {{ value }}
    </p>
    <p v-if="sublabel" class="text-sm text-gray-500 mt-1">{{ sublabel }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  sublabel?: string
  valueClass?: string
}>()
</script>
