<template>
  <div
    v-if="show"
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    @click="$emit('cancel')"
  >
    <div
      class="bg-white rounded-xl shadow-xl max-w-md w-[90%] max-h-[90vh] overflow-y-auto"
      @click.stop
    >
      <form class="p-6 space-y-4" @submit.prevent="submit">
        <h3 class="text-lg font-semibold text-gray-900">New goal</h3>

        <!-- Metric -->
        <label class="block">
          <span class="text-xs font-medium text-gray-700">Metric</span>
          <select v-model="metricKey" class="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm">
            <option v-for="t in types" :key="t.key" :value="t.key">{{ t.display_name }}</option>
          </select>
        </label>

        <!-- Kind -->
        <label class="block">
          <span class="text-xs font-medium text-gray-700">Type</span>
          <select v-model="kind" class="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm">
            <option value="volume">Volume — accumulate toward a total</option>
            <option value="frequency">Frequency — do it N times</option>
            <option value="streak">Streak — a daily chain</option>
          </select>
        </label>

        <!-- Period -->
        <label class="block">
          <span class="text-xs font-medium text-gray-700">Period</span>
          <select v-model="period" class="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm">
            <option value="week">This week</option>
            <option value="month">This month</option>
            <option value="year">This year</option>
            <option value="custom">Custom range</option>
          </select>
        </label>

        <div v-if="period === 'custom'" class="grid grid-cols-2 gap-3">
          <label class="block">
            <span class="text-xs font-medium text-gray-700">Start</span>
            <input v-model="periodStart" type="date" class="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" />
          </label>
          <label class="block">
            <span class="text-xs font-medium text-gray-700">End</span>
            <input v-model="periodEnd" type="date" class="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" />
          </label>
        </div>

        <!-- Target -->
        <label class="block">
          <span class="text-xs font-medium text-gray-700">{{ targetLabel }}</span>
          <input
            v-model.number="target"
            type="number"
            min="0"
            step="any"
            class="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
          />
        </label>

        <!-- Comparator (volume only) -->
        <label v-if="kind === 'volume'" class="block">
          <span class="text-xs font-medium text-gray-700">Goal direction</span>
          <select v-model="comparator" class="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm">
            <option value="gte">Reach at least the target</option>
            <option value="lte">Stay at or under the target</option>
          </select>
        </label>

        <!-- Rest budget (frequency / streak) -->
        <label v-if="kind !== 'volume'" class="block">
          <span class="text-xs font-medium text-gray-700">Rest days allowed (per window)</span>
          <input
            v-model.number="restBudget"
            type="number"
            min="0"
            class="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
          />
        </label>

        <p v-if="error" class="text-xs text-red-600">{{ error }}</p>

        <div class="flex justify-end gap-3 pt-2">
          <button type="button" class="btn-secondary text-sm" @click="$emit('cancel')">Cancel</button>
          <button
            type="submit"
            class="px-4 py-2 text-sm font-semibold text-white rounded-lg bg-brand-600 hover:bg-brand-700 disabled:opacity-50"
            :disabled="submitting || !valid"
          >
            {{ submitting ? 'Saving…' : 'Create goal' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMetrics, type NewGoalPayload } from '@/composables/useMetrics'
import type { MetricType } from '@/types/metrics'
import { displayUnit, toStored } from '@/utils/metrics'

const props = defineProps<{ show: boolean; types: MetricType[] }>()
const emit = defineEmits<{ created: []; cancel: [] }>()

const { createGoal } = useMetrics()

const metricKey = ref('')
const kind = ref('volume')
const period = ref('month')
const target = ref<number | null>(null)
const comparator = ref('gte')
const restBudget = ref(0)
const periodStart = ref('')
const periodEnd = ref('')
const submitting = ref(false)
const error = ref('')

const selectedType = computed(() => props.types.find((t) => t.key === metricKey.value))

// Default the metric once types arrive, and auto-pick a sensible direction.
watch(
  () => props.types,
  (t) => {
    if (!metricKey.value && t.length) metricKey.value = t[0].key
  },
  { immediate: true },
)
watch(metricKey, () => {
  comparator.value = selectedType.value && !selectedType.value.higher_is_better ? 'lte' : 'gte'
})

const targetLabel = computed(() => {
  if (kind.value === 'frequency') return 'How many times'
  if (kind.value === 'streak') return 'Target streak (days)'
  const u = selectedType.value ? displayUnit(selectedType.value.unit) : ''
  return `Target${u ? ` (${u})` : ''}`
})

const valid = computed(() => {
  if (!metricKey.value || target.value === null || target.value <= 0) return false
  if (period.value === 'custom' && (!periodStart.value || !periodEnd.value)) return false
  return true
})

async function submit(): Promise<void> {
  if (!valid.value || target.value === null) return
  submitting.value = true
  error.value = ''
  try {
    // Volume targets are in the metric's unit → convert display→stored.
    // Frequency/streak targets are plain counts.
    const storedTarget =
      kind.value === 'volume' && selectedType.value
        ? toStored(selectedType.value.unit, target.value)
        : target.value

    const payload: NewGoalPayload = {
      metric_key: metricKey.value,
      kind: kind.value,
      period: period.value,
      target: storedTarget,
      comparator: comparator.value,
    }
    if (kind.value !== 'volume') payload.rest_budget = restBudget.value
    if (period.value === 'custom') {
      payload.period_start = periodStart.value
      payload.period_end = periodEnd.value
    }

    await createGoal(payload)
    reset()
    emit('created')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to create goal'
  } finally {
    submitting.value = false
  }
}

function reset(): void {
  kind.value = 'volume'
  period.value = 'month'
  target.value = null
  restBudget.value = 0
  periodStart.value = ''
  periodEnd.value = ''
}
</script>
