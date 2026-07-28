<template>
  <div
    v-if="visible"
    class="bg-white rounded-xl border border-gray-100 shadow-sm p-6 mt-4"
    data-testid="route-frequency"
  >
    <div class="flex items-start justify-between flex-wrap gap-3">
      <div>
        <h2 class="font-semibold text-gray-900">You've run this route</h2>
        <p class="text-xs text-gray-400 mt-0.5">
          #{{ route!.rank }} of {{ route!.total_routes }} routes by how often you run it
        </p>
      </div>
      <p class="text-3xl font-bold text-gray-900">
        {{ route!.run_count }}<span class="text-base font-normal text-gray-400"> times</span>
      </p>
    </div>

    <div class="grid grid-cols-2 gap-3 mt-5">
      <div class="bg-gray-50 rounded-lg px-4 py-3">
        <p class="text-xs text-gray-500">This version</p>
        <p class="text-lg font-semibold text-gray-900">
          {{ route!.variant_run_count }}<span class="text-xs font-normal text-gray-400"> of {{ route!.run_count }}</span>
        </p>
      </div>
      <div class="bg-gray-50 rounded-lg px-4 py-3">
        <p class="text-xs text-gray-500">Best on this route</p>
        <p class="text-lg font-semibold text-gray-900">{{ formatPace(route!.best_pace_min_per_km, unit) }}</p>
      </div>
    </div>

    <p v-if="variantNote" class="text-xs text-gray-500 mt-3">{{ variantNote }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RunRoute, Unit } from '@/types/runs'
import { formatPace } from '@/utils/format'

const props = defineProps<{ route?: RunRoute | null; unit: Unit }>()

/**
 * Only shown when the count means what it says.
 *
 * variant_run_count is present only when the backend identified the route by
 * the path it traced (SB-396). Without that, run_count lumps together every run
 * of roughly this distance starting near here — for a home-based runner that's
 * several different routes, so "you've run this 1009 times" would be a real
 * number answering a question nobody asked. A route run once isn't a repeat
 * either, so it stays hidden too.
 */
const visible = computed(
  () => props.route != null && props.route.variant_run_count != null && props.route.run_count > 1,
)

/** Names the family/variant split, but only when there is one to explain. */
const variantNote = computed(() => {
  const r = props.route
  if (!r?.variant_run_count || r.variant_run_count >= r.run_count) return null
  return `Counts your slight variations of this route together — you've run this exact version ${r.variant_run_count} time${r.variant_run_count === 1 ? '' : 's'}.`
})
</script>
