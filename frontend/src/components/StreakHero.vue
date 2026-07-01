<template>
  <div
    class="relative overflow-hidden rounded-2xl shadow-md text-white p-6 h-full"
    :class="gradientClass"
  >
    <div class="absolute inset-0 opacity-20">
      <div class="absolute -top-12 -right-12 w-56 h-56 rounded-full bg-white blur-3xl" />
      <div class="absolute -bottom-16 -left-8 w-56 h-56 rounded-full bg-white blur-3xl" />
    </div>

    <div class="relative flex flex-col h-full">
      <div class="flex items-center gap-2 text-white/80 text-xs font-semibold uppercase tracking-wide mb-1">
        <span class="text-lg">🔥</span>
        <span>Current streak</span>
      </div>
      <p class="text-5xl sm:text-6xl font-extrabold leading-none tabular-nums">
        {{ animatedCurrent }}
      </p>
      <p class="text-white/80 text-sm mt-1">
        {{ current === 1 ? 'day' : 'days' }} of running
      </p>
      <p v-if="currentDistance" class="text-white font-semibold text-sm mt-2">
        {{ currentDistance }} this streak
      </p>

      <div class="mt-auto pt-4 border-t border-white/15">
        <p class="text-white/70 text-[11px] font-semibold uppercase tracking-wide">
          Longest streak
        </p>
        <p class="text-2xl font-bold tabular-nums leading-tight">
          {{ animatedLongest }}
          <span class="text-white/70 text-sm font-normal ml-1">
            {{ longest === 1 ? 'day' : 'days' }}
          </span>
        </p>
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
  currentDistance?: string
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
