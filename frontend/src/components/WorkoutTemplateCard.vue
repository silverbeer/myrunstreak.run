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
            <!-- Rounds only when the template's own count still means something:
                 a circuit template keeps rounds = 1 while its real counts live
                 on its blocks, so this read "1 Round" on a workout done twice
                 (SB-543). -->
            <Repeat class="w-3 h-3" /> {{ template.type
            }}<template v-if="showTemplateRounds">
              · {{ template.rounds }} {{ template.rounds === 1 ? 'round' : 'rounds' }}</template>
          </span>
          <span
            v-if="template.scheduled_for"
            class="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-700"
          >
            <Calendar class="w-3 h-3" /> {{ formatDayMonth(template.scheduled_for) }}
          </span>
          <!-- Who authored it (SB-486). Coaches see at a glance which workouts
               the athlete added themselves. -->
          <span
            v-if="authorLabel"
            class="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-xs font-semibold text-violet-700"
            data-testid="author-badge"
          >
            {{ authorLabel }}
          </span>
          <!-- On a list of plans, how often it has been done says more than
               whether it ever was — "done 5×" gives the library a history, and
               "not yet" reads as a nudge rather than a failure (SB-530). The
               coach views pass no count and keep the completion pill. -->
          <span
            v-if="showUsage"
            class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
            :class="usageCount > 0 ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'"
            data-testid="usage-count"
          >
            <Check v-if="usageCount > 0" class="w-3 h-3" />
            {{ usageCount > 0 ? `done ${usageCount}×` : 'not yet' }}
          </span>
          <span
            v-else-if="template.has_session"
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
      <div v-if="showActions" class="flex items-center gap-1 shrink-0 print:hidden">
        <button
          v-if="mayLog"
          type="button"
          class="act hover:text-brand-600 hover:bg-brand-50"
          title="Log this"
          aria-label="Log this workout"
          data-testid="log-this"
          @click="$emit('log')"
        >
          <ClipboardCheck class="w-4 h-4" />
        </button>
        <button v-if="mayPrint" type="button" class="act" title="Print" aria-label="Print workout" @click="$emit('print')">
          <Printer class="w-4 h-4" />
        </button>
        <button v-if="mayEdit" type="button" class="act" title="Edit" aria-label="Edit workout" @click="$emit('edit')">
          <Pencil class="w-4 h-4" />
        </button>
        <button
          v-if="mayEdit"
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
        <!-- Circuits, where the athlete actually looks. They have been data
             since SB-527 and visible only on the print sheet since SB-528, so
             the screen has been saying "1 Round" about a workout done twice
             (SB-543). -->
        <div v-for="(g, gi) in sec.groups" :key="g.block?.id ?? `loose-${gi}`">
          <div
            v-if="g.block"
            class="mt-2 mb-1 flex items-baseline gap-2 text-[11px] font-bold uppercase tracking-wide text-brand-700"
            data-testid="circuit-bar"
          >
            {{ g.block.label }}
            <span v-if="g.rounds > 1" class="text-gray-400">×{{ g.rounds }}</span>
          </div>
        <ul>
          <template v-for="(row, ri) in g.rows" :key="row.kind === 'group' ? row.key : row.item.id">
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
            class="group py-1.5 px-2 -mx-2 rounded-lg hover:bg-gray-50 transition-colors print:hover:bg-transparent"
            :class="row.kind === 'group' ? 'pl-6' : ''"
          >
            <div class="flex items-center justify-between gap-3">
              <!-- The name itself is the tap target (SB-525): a line of text is
                   a far better target mid-workout than a small icon would be. -->
              <button
                type="button"
                class="flex items-center gap-2 min-w-0 text-left py-1 -my-1 print:pointer-events-none"
                :aria-expanded="isOpen(item.id)"
                :data-testid="`describe-${item.exercise_key}`"
                @click="toggle(item.id)"
              >
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
                <Info class="w-3.5 h-3.5 shrink-0 text-gray-300 print:hidden" aria-hidden="true" />
              </button>
              <span class="flex items-center gap-1.5 shrink-0">
                <span v-for="p in pills(item)" :key="p.text" class="pill" :class="p.cls">{{ p.text }}</span>
              </span>
            </div>
            <ExerciseDescription
              v-if="isOpen(item.id)"
              class="mt-1.5 ml-7 print:hidden"
              :exercise="byKey[item.exercise_key]"
            />
          </li>
          </template>
        </ul>
          <!-- The four-minute water break is prescription, not decoration. -->
          <p
            v-if="g.restAfter"
            class="mt-1 mb-1 text-[11px] font-medium text-gray-400"
            data-testid="circuit-rest"
          >
            Rest {{ fmtRest(g.restAfter) }}
          </p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Calendar, Check, ClipboardCheck, Info, Pencil, Printer, Repeat, Trash2 } from 'lucide-vue-next'
import type { Exercise, TemplateItem, WorkoutSectionKey, WorkoutTemplate } from '@/types/workout'
import ExerciseDescription from '@/components/ExerciseDescription.vue'
import { SECTIONS, prettifyKey } from '@/utils/workoutPayload'
import { groupOptionItems } from '@/utils/optionGroups'
import { groupByBlock, roundsFor, templateRoundsAreMeaningful } from '@/utils/circuits'
import { targetPills } from '@/utils/targets'
import { formatDayMonth, formatRelativeTime } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    template: WorkoutTemplate
    exercises?: Exercise[]
    // Athlete-facing view (SB-332): hide the coach action buttons.
    readonly?: boolean
    // Finer-grained rights (SB-486). An athlete may log against and print a
    // workout their coach prescribed, but only edit one they authored — a
    // single `readonly` boolean could not express that, and it hid Print, which
    // the paper-first workflow depends on. Undefined = follow `readonly`, so
    // every existing caller behaves exactly as before.
    canLog?: boolean
    canPrint?: boolean
    canEdit?: boolean
    // e.g. "Added by Gabe" — the caller knows the names, the card just shows it.
    authoredBy?: string | null
    // Show "done N×" / "not yet" instead of the completion pill (SB-530).
    // Opt-in so the coach views are untouched: `false` is a real count.
    showUsage?: boolean
  }>(),
  {
    canLog: undefined,
    canPrint: undefined,
    canEdit: undefined,
    authoredBy: null,
    showUsage: false,
  },
)

/** Shown when a caller supplies it — the coach view labels athlete-authored rows. */
const authorLabel = computed(() => props.authoredBy ?? null)

/** How many sessions were logged against this plan (SB-530). */
const showUsage = computed(() => props.showUsage)
const usageCount = computed(() => props.template.session_count ?? 0)

const mayLog = computed(() => props.canLog ?? !props.readonly)
const mayPrint = computed(() => props.canPrint ?? !props.readonly)
const mayEdit = computed(() => props.canEdit ?? !props.readonly)
const showActions = computed(() => mayLog.value || mayPrint.value || mayEdit.value)

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
    // Circuits first, then alternatives within each — the same order the print
    // sheet resolves them in, via the same helper (SB-543).
    groups: groupByBlock(byKey.get(key)!, props.template.blocks ?? []).map((g) => ({
      block: g.block,
      rounds: roundsFor(g, props.template.rounds),
      restAfter: g.block?.rest_after_seconds ?? null,
      rows: groupOptionItems(g.items),
    })),
    items: byKey.get(key)!,
  }))
})

const pills = targetPills

/**
 * Whether to show the template's own round count in the header.
 *
 * A template whose rounds live on its blocks keeps `rounds = 1`, so the pill
 * read "Circuit · 1 Round" on a workout that is two circuits done twice —
 * stating the opposite of the prescription (SB-543).
 */
const showTemplateRounds = computed(() => templateRoundsAreMeaningful(props.template.blocks))

/** "4:00" — the rest between circuits, as the coach wrote it. */
const fmtRest = (seconds: number): string => {
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return m ? `${m}:${String(s).padStart(2, '0')}` : `${s}s`
}

// Which exercises have their description open. Per-item rather than one at a
// time: an athlete comparing "Side plank (L)" with "(R)" should be able to see
// both, and closing one to read another is friction mid-workout (SB-525).
const openItems = ref(new Set<string>())
const isOpen = (id: string) => openItems.value.has(id)
const toggle = (id: string) => {
  const next = new Set(openItems.value)
  next.has(id) ? next.delete(id) : next.add(id)
  openItems.value = next
}

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
