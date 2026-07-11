<template>
  <div
    v-if="variant === 'coach'"
    class="bg-white rounded-xl border border-gray-100 shadow-sm p-10 text-center"
  >
    <ClipboardList class="w-12 h-12 mx-auto mb-4 text-brand-600" />
    <h2 class="text-xl font-bold text-gray-900 mb-2">You're set up as a coach</h2>
    <p class="text-gray-500 max-w-md mx-auto mb-6">
      This dashboard tracks your own runs. Your athletes, workouts, and logged
      sessions live in the Coach area.
    </p>
    <RouterLink
      to="/coach"
      class="inline-block px-4 py-2 rounded-lg bg-brand-600 text-white font-medium hover:bg-brand-700"
    >
      Go to Coach
    </RouterLink>
  </div>

  <div v-else class="bg-white rounded-xl border border-gray-100 shadow-sm p-10 text-center">
    <Footprints class="w-12 h-12 mx-auto mb-4 text-brand-600" />
    <h2 class="text-xl font-bold text-gray-900 mb-2">Connect SmashRun to import your runs</h2>
    <p class="text-gray-500 max-w-md mx-auto mb-6">
      MyRunStreak pulls your activity from SmashRun. Authorize SmashRun once and we'll
      keep your runs and streak in sync.
    </p>
    <SyncButton mode="full" @synced="$emit('synced')" />
  </div>
</template>

<script setup lang="ts">
import { Footprints, ClipboardList } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'
import SyncButton from './SyncButton.vue'

withDefaults(defineProps<{ variant?: 'runner' | 'coach' }>(), { variant: 'runner' })

defineEmits<{ synced: [] }>()
</script>
