<template>
  <div class="bg-white rounded-2xl shadow-md p-6 border border-gray-100">
    <div class="flex items-center gap-2 mb-4">
      <Zap class="w-4 h-4 text-gray-700" />
      <h3 class="text-sm font-semibold uppercase tracking-wide text-gray-700">
        Quick log
      </h3>
    </div>

    <!-- Push-ups: one-tap presets + custom -->
    <div class="mb-5">
      <div class="flex items-center justify-between mb-2">
        <span class="inline-flex items-center gap-1 text-xs font-medium text-gray-700">
          <Dumbbell class="w-3.5 h-3.5" /> Push-ups
        </span>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-for="n in presets"
          :key="n"
          type="button"
          class="px-3 py-1.5 rounded-lg bg-brand-50 text-brand-700 text-sm font-medium hover:bg-brand-100 disabled:opacity-50"
          :disabled="submitting"
          @click="log('pushups', n)"
        >
          +{{ n }}
        </button>
        <div class="flex items-center gap-1">
          <input
            v-model.number="pushupCustom"
            type="number"
            min="1"
            inputmode="numeric"
            class="w-20 px-2 py-1.5 rounded-lg border border-gray-200 text-sm"
            placeholder="reps"
          />
          <button
            type="button"
            class="px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200 disabled:opacity-50"
            :disabled="submitting || !pushupCustom || pushupCustom < 1"
            @click="pushupCustom && log('pushups', pushupCustom)"
          >
            Log
          </button>
        </div>
      </div>
    </div>

    <!-- Body weight: number entry (display unit lb) -->
    <div>
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-medium text-gray-700">⚖️ Weigh-in</span>
      </div>
      <div class="flex items-center gap-2">
        <input
          v-model.number="weight"
          type="number"
          min="1"
          step="0.1"
          inputmode="decimal"
          class="w-28 px-2 py-1.5 rounded-lg border border-gray-200 text-sm"
          :placeholder="weightUnit"
        />
        <span class="text-xs text-gray-400">{{ weightUnit }}</span>
        <button
          type="button"
          class="px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200 disabled:opacity-50"
          :disabled="submitting || !weight || weight <= 0"
          @click="logWeight"
        >
          Log
        </button>
      </div>
    </div>

    <p v-if="confirmation" class="mt-3 text-xs text-green-600">{{ confirmation }}</p>
    <p v-if="error" class="mt-3 text-xs text-red-600">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Dumbbell, Zap } from 'lucide-vue-next'
import { useMetrics } from '@/composables/useMetrics'
import type { MetricType } from '@/types/metrics'
import { displayUnit, toStored } from '@/utils/metrics'

const props = defineProps<{ types: MetricType[] }>()
const emit = defineEmits<{ logged: [] }>()

const { logEntry } = useMetrics()

const presets = [10, 25, 50]
const pushupCustom = ref<number | null>(null)
const weight = ref<number | null>(null)
const submitting = ref(false)
const confirmation = ref('')
const error = ref('')

const weightStoredUnit = computed(
  () => props.types.find((t) => t.key === 'body_weight')?.unit ?? 'kg',
)
const weightUnit = computed(() => displayUnit(weightStoredUnit.value))

async function log(metricKey: string, value: number): Promise<void> {
  if (submitting.value || !value || value <= 0) return
  submitting.value = true
  confirmation.value = ''
  error.value = ''
  try {
    await logEntry(metricKey, value)
    confirmation.value = 'Logged ✓'
    pushupCustom.value = null
    emit('logged')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to log'
  } finally {
    submitting.value = false
  }
}

async function logWeight(): Promise<void> {
  if (!weight.value || weight.value <= 0) return
  const stored = toStored(weightStoredUnit.value, weight.value)
  await log('body_weight', stored)
  weight.value = null
}
</script>
