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
          <span v-if="template.source" class="text-xs text-gray-400">Coached by {{ template.source }}</span>
        </div>
      </div>
      <div class="flex items-center gap-1 shrink-0 print:hidden">
        <button type="button" class="act" title="Print" aria-label="Print workout" @click="print">
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
          <li
            v-for="(item, i) in sec.items"
            :key="item.id"
            class="group flex items-center justify-between gap-3 py-1.5 px-2 -mx-2 rounded-lg hover:bg-gray-50 transition-colors print:hover:bg-transparent"
          >
            <span class="flex items-center gap-2 min-w-0">
              <span
                v-if="sec.key === 'main'"
                class="w-5 h-5 shrink-0 grid place-items-center rounded-full bg-brand-50 text-brand-700 text-[11px] font-semibold tabular-nums"
              >
                {{ i + 1 }}
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
        </ul>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Pencil, Printer, Repeat, Trash2 } from 'lucide-vue-next'
import type { Exercise, TemplateItem, WorkoutSectionKey, WorkoutTemplate } from '@/types/workout'
import { SECTIONS, fmtDuration, kgToLb, prettifyKey } from '@/utils/workoutPayload'

const props = defineProps<{
  template: WorkoutTemplate
  exercises?: Exercise[]
}>()

defineEmits<{ (e: 'edit'): void; (e: 'delete'): void }>()

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

const sections = computed(() =>
  SECTIONS.map((s) => ({
    key: s.key,
    title: s.label,
    ...ACCENT[s.key],
    items: props.template.items
      .filter((it) => it.section === s.key)
      .sort((a, b) => a.position - b.position),
  })).filter((s) => s.items.length > 0),
)

interface Pill {
  text: string
  cls: string
}
const pills = (it: TemplateItem): Pill[] => {
  const out: Pill[] = []
  const base = 'bg-gray-100 text-gray-600'
  if (it.target_reps != null) out.push({ text: `${it.target_reps} reps`, cls: base })
  if (it.target_duration_seconds != null)
    out.push({ text: fmtDuration(it.target_duration_seconds), cls: base })
  if (it.target_load_kg != null)
    out.push({ text: `${kgToLb(it.target_load_kg)} lb`, cls: 'bg-amber-50 text-amber-700' })
  if (it.target_distance_m != null) out.push({ text: `${it.target_distance_m} m`, cls: base })
  if (it.rest_seconds != null)
    out.push({ text: `rest ${fmtDuration(it.rest_seconds)}`, cls: 'bg-gray-50 text-gray-400' })
  return out
}

const rootEl = ref<HTMLElement | null>(null)

// Print just this card on its own page: mark it + <body>, print, then clean up.
const print = (): void => {
  const el = rootEl.value
  if (!el) {
    window.print()
    return
  }
  document.body.classList.add('printing-card')
  el.classList.add('print-target')
  const cleanup = (): void => {
    document.body.classList.remove('printing-card')
    el.classList.remove('print-target')
    window.removeEventListener('afterprint', cleanup)
  }
  window.addEventListener('afterprint', cleanup)
  window.print()
}
</script>

<style scoped>
.act {
  @apply p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors;
}
.pill {
  @apply rounded-md px-1.5 py-0.5 text-[11px] font-medium tabular-nums whitespace-nowrap;
}
</style>
