<template>
  <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-10 text-center">
    <div class="text-5xl mb-4">🏃</div>
    <h2 class="text-xl font-bold text-gray-900 mb-2">Connect SmashRun to import your runs</h2>
    <p class="text-gray-500 max-w-md mx-auto mb-6">
      MyRunStreak pulls your activity from SmashRun. Authorize SmashRun once and we'll
      keep your runs and streak in sync.
    </p>
    <SyncButton mode="full" @synced="$emit('synced')" />
  </div>
</template>

<script setup lang="ts">
import SyncButton from './SyncButton.vue'

defineEmits<{ synced: [] }>()
</script>
