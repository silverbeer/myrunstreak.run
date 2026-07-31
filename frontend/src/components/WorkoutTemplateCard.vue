<template>
  <div
    ref="rootEl"
    class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden print:shadow-none print:border-gray-300"
  >
    <!-- Header -->
    <div class="flex items-start justify-between gap-3 p-5 border-b border-gray-100">
      <div class="min-w-0">
        <h3 class="text-lg font-bold text-gray-900 leading-tight">{{ template.name }}</h3>
        <div class="mt-1.5 flex flex-wrap items-center gap-2">
          <span class="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-700 capitalize">
            <Repeat class="w-3 h-3" /> {{ template.type }} · {{ template.rounds }} {{ template.rounds === 1 ? 'round' : 'rounds' }}
          </span>
          <span
            v-if="template.scheduled_for"
            class="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-700"
          >
            <Calendar class="w-3 h-3" /> {{ formatDayMonth(template.scheduled_for) }}
          </span>
          <span
            v-if="template.has_session"
            class="inline-flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-xs font-semibold text-green-700"
          >
            <Check class="w-3 h-3" /> Completed<template v-if="template.last_session_date"> · {{ formatDayMonth(template.last_session_date) }}</template>
          </span>
          <span
            v-else
            class="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500"
          >
            Not logged
          </span>
          <span v-if="template.source" class="text-xs text-gray-400">Coached by {{ template.source }}</span>
        </div>
        <p v-if="template.created_at" class="mt-1 text-xs text-gray-400">
          Added {{ formatRelativeTime(template.created_at) }}
        </p>
      </div>
      <div v-if="!readonly" class="flex items-center gap-1 shrink-0 print:hidden">
        <button
          type="button"
          class="act hover:text-brand-600 hover:bg-brand-50"
          title="Log this"
          aria-label="Log this workout"
          data-testid="log-this"
          @click="$emit('log')"
        >
          <ClipboardCheck class="w-4 h-4" />
        </button>
        <button type="button" class="act" title="Print" aria-label="Print workout" @click="$emit('print')">
          <Printer class="w-4 h-4" />
        </button>
        <button type="button" class="act" title="Edit" aria-label="Edit workout" @click="$emit('edit')">
          <Pencil class="w-4 h-4" />
        </button>
        <button
          type="button"
          class="act hover:text-red-600 hover:bg-red-50"
          title="Delete"
          aria-label="Delete workout"
          @click="$emit('delete')"
        >
          <Trash2 class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- Sections -->
    <div class="p-5 space-y-5">
      <section v-for="sec in sections" :key="sec.key" class="border-l-2 pl-3" :class="sec.rule">
        <h4 class="text-[11px] font-bold uppercase tracking-wider mb-1.5" :class="sec.label">
          {{ sec.title }}
          <span class="text-gray-300 font-medium">· {{ sec.items.length }}</span>
        </h4>
        <ul>
          <template v-for="(row, ri) in sec.rows" :key="row.kind === 'group' ? row.key : row.item.id">
            <!-- Alternatives are one choice, not a checklist (SB-448). -->
            <li
              v-if="row.kind === 'group'"
              class="flex items-center gap-2 pt-1.5 pb-0.5 px-2 -mx-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400"
            >
              {{ row.label }} · do one
            </li>
          <li
            v-for="item in row.kind === 'group' ? row.items : [row.item]"
            :key="item.id"
            class="group flex items-center justify-between gap-3 py-1.5 px-2 -mx-2 rounded-lg hover:bg-gray-50 transition-colors print:hover:bg-transparent"
            :class="row.kind === 'group' ? 'pl-6' : ''"
          >
            <span class="flex items-center gap-2 min-w-0">
              <span
                v-if="row.kind === 'group'"
                class="w-5 h-5 shrink-0 grid place-items-center text-gray-300 text-[11px]"
              >
                ○
              </span>
              <span
                v-else-if="sec.key === 'main'"
                class="w-5 h-5 shrink-0 grid place-items-center rounded-full bg-brand-50 text-brand-700 text-[11px] font-semibold tabular-nums"
              >
                {{ ri + 1 }}
              </span>
              <span class="text-sm text-gray-900 truncate">{{ nameFor(item.exercise_key) }}</span>
              <span
                v-if="item.variant"
                class="shrink-0 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500 capitalize"
              >
                {{ item.variant }}
              </span>
            </span>
            <span class="flex items-center gap-1.5 shrink-0">
              <span v-for="p in pills(item)" :key="p.text" class="pill" :class="p.cls">{{ p.text }}</span>
            </span>
          </li>
          </template>
        </ul>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Calendar, Check, ClipboardCheck, Pencil, Printer, Repeat, Trash2 } from 'lucide-vue-next'
import type { Exercise, TemplateItem, WorkoutSectionKey, WorkoutTemplate } from '@/types/workout'
import { SECTIONS, prettifyKey } from '@/utils/workoutPayload'
import { groupOptionItems } from '@/utils/optionGroups'
import { targetPills } from '@/utils/targets'
import { formatDayMonth, formatRelativeTime } from '@/utils/format'

const props = defineProps<{
  template: WorkoutTemplate
  exercises?: Exercise[]
  // Athlete-facing view (SB-332): hide the coach action buttons.
  readonly?: boolean
}>()

defineEmits<{ (e: 'edit'): void; (e: 'delete'): void; (e: 'log'): void; (e: 'print'): void }>()

const byKey = computed<Record<string, Exercise>>(() => {
  const map: Record<string, Exercise> = {}
  for (const ex of props.exercises ?? []) map[ex.key] = ex
  return map
})
const nameFor = (key: string): string => byKey.value[key]?.display_name ?? prettifyKey(key)

// Per-section accent (subtle): warm-up amber, main navy, cool-down sky.
const ACCENT: Record<WorkoutSectionKey, { rule: string; label: string }> = {
  warmup: { rule: 'border-amber-300', label: 'text-amber-600' },
  main: { rule: 'border-brand-400', label: 'text-brand-700' },
  cooldown: { rule: 'border-sky-300', label: 'text-sky-600' },
}

const KNOWN = new Set(SECTIONS.map((s) => s.key as string))
const FALLBACK_ACCENT = { rule: 'border-gray-200', label: 'text-gray-500' }

/**
 * Every section the template actually uses (SB-484).
 *
 * `section` is free text, but this used to filter against a fixed
 * warmup/main/cooldown whitelist — so a plan with a `speed_endurance` block
 * silently rendered without its intervals, and the athlete had no way to know
 * anything was missing. Known sections keep their order and accent; anything
 * else follows, in the order the items appear.
 */
const sections = computed(() => {
  const byKey = new Map<string, TemplateItem[]>()
  for (const it of [...props.template.items].sort((a, b) => a.position - b.position)) {
    const key = it.section || 'main'
    if (!byKey.has(key)) byKey.set(key, [])
    byKey.get(key)!.push(it)
  }
  const keys = [
    ...SECTIONS.map((s) => s.key as string).filter((k) => byKey.has(k)),
    ...[...byKey.keys()].filter((k) => !KNOWN.has(k)),
  ]
  return keys.map((key) => ({
    key,
    title: SECTIONS.find((s) => s.key === key)?.label ?? prettifyKey(key),
    ...(ACCENT[key as WorkoutSectionKey] ?? FALLBACK_ACCENT),
    rows: groupOptionItems(byKey.get(key)!),
    items: byKey.get(key)!,
  }))
})

const pills = targetPills

const rootEl = ref<HTMLElement | null>(null)

</script>

<style scoped>
.act {
  @apply p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors;
}
.pill {
  @apply rounded-md px-1.5 py-0.5 text-[11px] font-medium tabular-nums whitespace-nowrap;
}
</style>
