<template>
  <div
    class="relative overflow-hidden rounded-2xl shadow-md text-white p-8 sm:p-10 mb-6"
    :class="gradientClass"
  >
    <div class="absolute inset-0 opacity-20">
      <div class="absolute -top-16 -right-16 w-72 h-72 rounded-full bg-white blur-3xl" />
      <div class="absolute -bottom-20 -left-10 w-72 h-72 rounded-full bg-white blur-3xl" />
    </div>

    <div class="relative flex flex-col sm:flex-row items-start sm:items-end justify-between gap-6">
      <div>
        <div class="flex items-center gap-2 text-white/80 text-sm font-semibold uppercase tracking-wide mb-1">
          <span class="text-xl">🔥</span>
          <span>Current streak</span>
        </div>
        <p class="text-7xl sm:text-8xl font-extrabold leading-none tabular-nums">
          {{ animatedCurrent }}
        </p>
        <p class="text-white/80 text-base mt-2">
          {{ current === 1 ? 'day' : 'days' }} of running
        </p>
      </div>

      <div class="sm:text-right">
        <p class="text-white/70 text-xs font-semibold uppercase tracking-wide">
          Longest streak
        </p>
        <p class="text-3xl sm:text-4xl font-bold tabular-nums">
          {{ animatedLongest }}
        </p>
        <p class="text-white/70 text-sm">{{ longest === 1 ? 'day' : 'days' }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue'
import { useCountUp } from '@/composables/useCountUp'

const props = defineProps<{
  current: number
  longest: number
}>()

const currentRef = toRef(props, 'current')
const longestRef = toRef(props, 'longest')

const animatedCurrent = useCountUp(() => currentRef.value)
const animatedLongest = useCountUp(() => longestRef.value)

const gradientClass = computed(() => {
  if (props.current >= 30) return 'bg-gradient-to-br from-red-600 via-orange-500 to-amber-400'
  if (props.current >= 7) return 'bg-gradient-to-br from-orange-600 via-orange-500 to-amber-400'
  if (props.current >= 1) return 'bg-gradient-to-br from-orange-500 to-amber-300'
  return 'bg-gradient-to-br from-gray-500 to-gray-400'
})
</script>
