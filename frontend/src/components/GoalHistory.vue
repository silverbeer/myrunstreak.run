<template>
  <div class="bg-white rounded-2xl shadow-md border border-gray-100">
    <!-- Header / toggle -->
    <button
      type="button"
      class="w-full flex items-center justify-between gap-2 p-6 text-left"
      :aria-expanded="open"
      @click="toggle"
    >
      <span class="inline-flex items-center gap-2">
        <History class="w-4 h-4 text-gray-700" />
        <span class="text-sm font-semibold uppercase tracking-wide text-gray-700">
          Goal history
        </span>
      </span>
      <ChevronDown
        class="w-4 h-4 text-gray-400 transition-transform duration-200"
        :class="{ 'rotate-180': open }"
      />
    </button>

    <div v-if="open" class="px-6 pb-6">
      <div v-if="loading" class="text-sm text-gray-500 py-2">Loading history…</div>
      <div v-else-if="!groups.length" class="text-sm text-gray-500 py-2">
        No past goals yet.
      </div>

      <div v-else class="space-y-6">
        <div v-for="g in groups" :key="g.year">
          <!-- Year header (yearly goal, if any) -->
          <div class="flex items-center justify-between gap-2 mb-2 pb-1 border-b border-gray-100">
            <span class="inline-flex items-center gap-1.5 text-sm font-semibold text-gray-900">
              <Target class="w-4 h-4 text-brand-600" /> {{ g.year }}
            </span>
            <span v-if="g.yearly" class="inline-flex items-center gap-2 text-xs">
              <span class="font-medium text-gray-900 whitespace-nowrap">
                {{ g.yearly.progress_mi.toFixed(0) }} / {{ g.yearly.goal_mi.toFixed(0) }} mi
              </span>
              <span :class="badgeClass(g.yearly)">{{ badgeLabel(g.yearly) }}</span>
            </span>
          </div>

          <!-- Month rows -->
          <ul class="divide-y divide-gray-50">
            <li
              v-for="m in g.months"
              :key="m.month ?? 0"
              class="flex items-center gap-3 py-2"
            >
              <span class="w-10 shrink-0 text-xs font-medium text-gray-600">
                {{ monthLabel(m.month) }}
              </span>

              <div class="flex-1 min-w-0">
                <div class="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                  <div
                    class="h-1.5 rounded-full"
                    :class="barClass(m)"
                    :style="{ width: Math.min(pct(m), 100) + '%' }"
                  ></div>
                </div>
              </div>

              <span class="w-24 shrink-0 text-right text-xs text-gray-700 whitespace-nowrap tabular-nums">
                {{ m.progress_mi.toFixed(0) }} / {{ m.goal_mi.toFixed(0) }} mi
              </span>
              <span class="w-16 shrink-0 text-right text-xs tabular-nums" :class="pctColor(m)">
                {{ pct(m).toFixed(0) }}%
              </span>
              <span class="w-16 shrink-0 text-right">
                <span :class="badgeClass(m)">{{ badgeLabel(m) }}</span>
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, History, Target } from 'lucide-vue-next'
import type { GoalHistoryItem } from '@/types/runs'

const props = defineProps<{
  items: GoalHistoryItem[]
  loading: boolean
}>()

const emit = defineEmits<{ (e: 'expand'): void }>()

const open = ref(false)
const toggle = (): void => {
  open.value = !open.value
  if (open.value) emit('expand') // parent lazy-loads; composable no-ops if already loaded
}

const MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const monthLabel = (m: number | null): string => (m ? MONTHS[m] : '')

const now = new Date()
const currentYear = now.getFullYear()
const currentMonth = now.getMonth() + 1

/** A period still in progress (this month / this year) — don't badge it "Missed". */
const isCurrent = (it: GoalHistoryItem): boolean =>
  it.year === currentYear && (it.period === 'year' || it.month === currentMonth)

const pct = (it: GoalHistoryItem): number =>
  it.goal_mi > 0 ? (it.progress_mi / it.goal_mi) * 100 : 0

interface YearGroup {
  year: number
  yearly: GoalHistoryItem | null
  months: GoalHistoryItem[]
}

const groups = computed((): YearGroup[] => {
  const byYear = new Map<number, YearGroup>()
  for (const it of props.items) {
    let g = byYear.get(it.year)
    if (!g) {
      g = { year: it.year, yearly: null, months: [] }
      byYear.set(it.year, g)
    }
    if (it.period === 'year') g.yearly = it
    else g.months.push(it)
  }
  // Backend already orders year desc, month desc — preserve insertion order.
  return [...byYear.values()]
})

const badgeLabel = (it: GoalHistoryItem): string => {
  if (it.hit) return 'Hit'
  if (isCurrent(it)) return 'Active'
  return 'Missed'
}

const badgeClass = (it: GoalHistoryItem): string => {
  const base = 'inline-block px-1.5 py-0.5 rounded text-[10px] font-medium '
  if (it.hit) return base + 'bg-green-100 text-green-700'
  if (isCurrent(it)) return base + 'bg-blue-100 text-blue-700'
  return base + 'bg-amber-100 text-amber-700'
}

const pctColor = (it: GoalHistoryItem): string => {
  if (it.hit) return 'text-green-600'
  if (isCurrent(it)) return 'text-gray-500'
  return 'text-amber-600'
}

const barClass = (it: GoalHistoryItem): string => {
  if (it.hit) return 'bg-green-500'
  if (isCurrent(it)) return 'bg-blue-500'
  return 'bg-amber-500'
}
</script>
