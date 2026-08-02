<template>
  <div class="container-app py-8 max-w-2xl">
    <div class="mb-4">
      <h1 class="text-2xl font-bold text-gray-900 mb-1">My training</h1>
      <p class="text-sm text-gray-500">What you're doing, and the plans behind it.</p>
    </div>

    <!-- Two tabs, and the whole point of them: "workout" meant both the plan and
         the doing, so "+ New workout" could not be read (SB-530). Splitting the
         nouns splits the verbs — building lives only where plans live, and the
         doing screen has exactly one primary control. -->
    <div class="flex gap-5 border-b border-gray-200 mb-5" role="tablist">
      <button
        type="button"
        role="tab"
        class="tab"
        :class="tab === 'training' ? 'tab-on' : ''"
        :aria-selected="tab === 'training'"
        data-testid="tab-training"
        @click="tab = 'training'"
      >
        Training
      </button>
      <button
        type="button"
        role="tab"
        class="tab"
        :class="tab === 'plans' ? 'tab-on' : ''"
        :aria-selected="tab === 'plans'"
        data-testid="tab-plans"
        @click="tab = 'plans'"
      >
        Plans
        <span v-if="templates.length" class="ml-1 text-xs font-medium text-gray-400 tabular-nums">
          {{ templates.length }}
        </span>
      </button>
    </div>

    <div v-if="loading" class="space-y-3">
      <div
        v-for="i in 3"
        :key="i"
        class="h-28 bg-white rounded-2xl border border-gray-100 animate-pulse"
      />
    </div>

    <div
      v-else-if="error"
      class="bg-red-50 border border-red-100 rounded-xl p-4 text-sm text-red-600"
    >
      {{ error }}
    </div>

    <!-- ------------------------------------------------------------- Training -->
    <div v-else-if="tab === 'training'" class="space-y-5">
      <!-- Due today gets the Start card. When nothing is scheduled, logging what
           you just did IS the primary action, not a quiet link under an empty
           section (SB-531). -->
      <div
        v-if="dueToday"
        class="rounded-2xl border border-brand-300 bg-white p-5 shadow-sm"
        data-testid="start-card"
      >
        <div class="flex items-start justify-between gap-3">
          <h2 class="text-lg font-bold text-gray-900 leading-tight">
            {{ dueToday.template.name }}
          </h2>
          <span
            class="shrink-0 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-amber-700"
          >
            {{ formatDayPill(dueToday.scheduled_for) }}
          </span>
        </div>
        <!-- Who put it on the day. Either side may schedule (SB-534), and a
             workout Gabe planned himself reads differently from one his coach
             expects of him — same vocabulary as the Plans grouping. -->
        <p class="mt-1 text-sm text-gray-500">
          <span data-testid="scheduled-by">{{ dueToday.by }}</span> · {{ planSummary(dueToday.template) }}
        </p>
        <button
          type="button"
          class="mt-3 w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
          data-testid="start-workout"
          @click="router.push(`/my/workouts/log/${dueToday.template.id}`)"
        >
          Start workout
        </button>
        <button
          type="button"
          class="mt-2 w-full rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-brand-700 hover:bg-gray-50"
          @click="router.push(`/my/workouts/print/${dueToday.template.id}`)"
        >
          Print sheet
        </button>
      </div>

      <div v-else class="rounded-2xl border border-brand-200 bg-brand-50 p-5 text-center">
        <p class="text-sm font-semibold text-brand-800">
          {{ nextUp ? 'Nothing scheduled today' : 'Did a workout on your own?' }}
        </p>
        <p v-if="nextUp" class="mt-1 text-sm text-brand-700">
          Next up: {{ nextUp.template.name }}, {{ formatDayPill(nextUp.scheduled_for) }}
        </p>
        <p v-else class="mt-1 text-sm text-brand-700">Log it and get the credit — no plan needed.</p>
        <RouterLink
          to="/my/workouts/log"
          class="mt-3 inline-block rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
          data-testid="log-adhoc"
        >
          + Log a workout
        </RouterLink>
        <p v-if="nextUp" class="mt-2 text-xs text-brand-700">
          Did something on your own? Get credit for it.
        </p>
      </div>

      <!-- Nothing is scheduled, so without this the plans are a tab away and the
           athlete has to find them — the same "finished but no door" failure
           that hid logging and athlete-authoring (SB-530). -->
      <button
        v-if="!dueToday && templates.length"
        type="button"
        class="w-full rounded-lg border border-gray-200 px-4 py-2 text-center text-sm font-medium text-brand-700 hover:bg-gray-50"
        data-testid="go-to-plans"
        @click="tab = 'plans'"
      >
        Or start one of your {{ templates.length }} plans
      </button>

      <!-- With a workout due, the ad-hoc path keeps its place as a quiet line
           beneath the Start card rather than disappearing (SB-531). -->
      <RouterLink
        v-if="dueToday"
        to="/my/workouts/log"
        class="block rounded-lg border border-gray-200 px-4 py-2 text-center text-sm font-medium text-brand-700 hover:bg-gray-50"
        data-testid="log-adhoc"
      >
        + Log something I just did
      </RouterLink>

      <!-- Scheduled work, soonest first. Every row says who put it there — a
           coach's Thursday and one the athlete planned themselves are not the
           same thing (SB-534). -->
      <section v-if="laterUp.length" data-testid="coming-up">
        <h2 class="group-label">Coming up</h2>
        <div class="rounded-2xl border border-gray-100 bg-white shadow-sm divide-y divide-gray-100">
          <div
            v-for="o in laterUp"
            :key="o.id"
            class="flex items-center gap-2 pr-2 hover:bg-gray-50"
            data-testid="coming-up-row"
          >
            <button
              type="button"
              class="min-w-0 flex-1 flex items-center justify-between gap-3 px-4 py-3 text-left"
              @click="router.push(`/my/workouts/log/${o.template.id}`)"
            >
              <span class="min-w-0">
                <span class="block font-semibold text-gray-900 truncate">
                  {{ o.template.name }}
                </span>
                <span class="block text-xs text-gray-500">
                  <span data-testid="scheduled-by">{{ o.by }}</span> · {{ planSummary(o.template) }}
                </span>
              </span>
              <span
                class="shrink-0 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-500"
              >
                {{ formatDayPill(o.scheduled_for) }}
              </span>
            </button>
            <!-- Only what you put there yourself. The API enforces the same
                 rule; this keeps the button honest (SB-486). -->
            <button
              v-if="o.mine"
              type="button"
              class="shrink-0 rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600"
              :aria-label="`Unschedule ${o.template.name}`"
              data-testid="unschedule"
              @click="unschedule(o)"
            >
              <X class="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      <section>
        <h2 class="group-label">
          <span>Completed ({{ completed.length }})</span>
          <span v-if="thisWeekCount" class="text-xs font-medium normal-case tracking-normal text-gray-400">
            {{ thisWeekCount }} this week
          </span>
        </h2>

        <div
          v-if="sessionsError"
          class="rounded-xl border border-amber-100 bg-amber-50 p-4 text-sm text-amber-700"
        >
          Couldn't load what you've done — {{ sessionsError }}
        </div>

        <div
          v-else-if="completed.length === 0"
          class="rounded-2xl border border-dashed border-gray-200 p-6 text-center"
          data-testid="completed-empty"
        >
          <p class="text-sm font-semibold text-gray-700">Nothing logged yet</p>
          <p class="mt-1 text-sm text-gray-500">
            Finish a workout and it lands here — with a count that only goes up.
          </p>
        </div>

        <div
          v-else
          class="rounded-2xl border border-gray-100 bg-white shadow-sm divide-y divide-gray-100"
        >
          <div
            v-for="row in visibleCompleted"
            :key="row.id"
            class="flex items-center justify-between gap-3 px-4 py-3"
            data-testid="completed-row"
          >
            <!-- Renaming after the fact (SB-536): the default is read off the
                 date, and only he knows which one was the garage circuit. -->
            <div v-if="renamingId === row.id" class="flex min-w-0 flex-1 items-center gap-2">
              <input
                v-model="renameText"
                type="text"
                maxlength="80"
                class="min-w-0 flex-1 rounded-lg border border-gray-200 px-2 py-1 text-sm"
                data-testid="rename-input"
                @keyup.enter="saveRename(row)"
              />
              <button
                type="button"
                class="shrink-0 rounded-lg bg-brand-600 px-3 py-1 text-xs font-semibold text-white"
                data-testid="rename-save"
                @click="saveRename(row)"
              >
                Save
              </button>
              <button
                type="button"
                class="shrink-0 rounded-lg border border-gray-200 px-3 py-1 text-xs font-medium text-gray-600"
                data-testid="rename-cancel"
                @click="renamingId = null"
              >
                Cancel
              </button>
            </div>

            <template v-else>
              <div class="min-w-0">
                <p class="font-semibold text-gray-900 truncate">{{ row.title }}</p>
                <p class="text-xs text-gray-500">{{ row.detail }}</p>
              </div>
              <span class="flex shrink-0 items-center gap-1">
                <!-- Only sessions with no plan behind them: one logged against
                     Matthew's workout is called what Matthew called it. -->
                <button
                  v-if="row.adhoc"
                  type="button"
                  class="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
                  :aria-label="`Rename ${row.title}`"
                  data-testid="rename-open"
                  @click="startRename(row)"
                >
                  <Pencil class="w-3.5 h-3.5" />
                </button>
                <span
                  class="rounded-full bg-green-50 px-2 py-0.5 text-xs font-semibold text-green-700"
                >
                  {{ row.when }}
                </span>
              </span>
            </template>
          </div>
          <button
            v-if="completed.length > COMPLETED_PREVIEW && !showAllCompleted"
            type="button"
            class="w-full px-4 py-2.5 text-sm font-medium text-brand-700 hover:bg-gray-50"
            data-testid="see-all-completed"
            @click="showAllCompleted = true"
          >
            See all {{ completed.length }}
          </button>
        </div>
      </section>
    </div>

    <!-- ---------------------------------------------------------------- Plans -->
    <div v-else class="space-y-5">
      <!-- "+ Build a workout" is unambiguous here and nowhere else: everything
           around it is already a plan (SB-530). -->
      <RouterLink
        to="/my/workouts/build"
        class="block rounded-lg border border-gray-200 px-4 py-2.5 text-center text-sm font-medium text-gray-700 hover:bg-gray-50"
        data-testid="build-workout"
      >
        + Build a workout
      </RouterLink>

      <section v-if="fromCoach.length" data-testid="group-from-coach">
        <h2 class="group-label">
          <span>{{ coachGroupLabel }}</span>
          <span class="tabular-nums">{{ fromCoach.length }}</span>
        </h2>
        <div class="space-y-4">
          <div v-for="t in fromCoach" :key="t.id">
            <WorkoutTemplateCard
              :template="t"
              :exercises="exercises"
              show-usage
              :can-log="false"
              can-print
              :can-edit="false"
              @print="router.push(`/my/workouts/print/${t.id}`)"
            />
            <!-- The "log this" icon was an unlabelled tooltip, which does not
                 exist on a phone — the most frequent action on the screen was
                 the least visible one (SB-530). -->
            <button
              type="button"
              class="mt-2 w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
              data-testid="start-workout"
              @click="router.push(`/my/workouts/log/${t.id}`)"
            >
              Start workout
            </button>
            <!-- Gabe plans his own week too — scheduling is not a coach-only
                 verb (SB-534). -->
            <!-- What repeats, and how to stop it (SB-535). -->
            <div
              v-if="repeatFor(t.id)"
              class="mt-2 flex items-center justify-between gap-2 rounded-lg bg-brand-50 px-3 py-2"
              data-testid="repeat-line"
            >
              <span class="text-xs font-semibold text-brand-800">
                {{ describeRepeat(repeatFor(t.id)!.byweekday) }}
              </span>
              <button
                type="button"
                class="text-xs font-medium text-brand-700 underline"
                data-testid="repeat-stop"
                @click="stopRepeat(repeatFor(t.id)!.id)"
              >
                Stop repeating
              </button>
            </div>
            <ScheduleWorkout
              v-if="athleteId"
              class="mt-2"
              :template-id="t.id"
              :athlete-id="athleteId"
              @scheduled="reloadSchedule"
            />
          </div>
        </div>
      </section>

      <section v-if="mine.length" data-testid="group-mine">
        <h2 class="group-label">
          <span>Mine</span>
          <span class="tabular-nums">{{ mine.length }}</span>
        </h2>
        <div class="space-y-4">
          <div v-for="t in mine" :key="t.id">
            <WorkoutTemplateCard
              :template="t"
              :exercises="exercises"
              show-usage
              :can-log="false"
              can-print
              can-edit
              @print="router.push(`/my/workouts/print/${t.id}`)"
              @edit="router.push(`/my/workouts/build/${t.id}`)"
              @delete="remove(t)"
            />
            <button
              type="button"
              class="mt-2 w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
              data-testid="start-workout"
              @click="router.push(`/my/workouts/log/${t.id}`)"
            >
              Start workout
            </button>
            <!-- Gabe plans his own week too — scheduling is not a coach-only
                 verb (SB-534). -->
            <!-- What repeats, and how to stop it (SB-535). -->
            <div
              v-if="repeatFor(t.id)"
              class="mt-2 flex items-center justify-between gap-2 rounded-lg bg-brand-50 px-3 py-2"
              data-testid="repeat-line"
            >
              <span class="text-xs font-semibold text-brand-800">
                {{ describeRepeat(repeatFor(t.id)!.byweekday) }}
              </span>
              <button
                type="button"
                class="text-xs font-medium text-brand-700 underline"
                data-testid="repeat-stop"
                @click="stopRepeat(repeatFor(t.id)!.id)"
              >
                Stop repeating
              </button>
            </div>
            <ScheduleWorkout
              v-if="athleteId"
              class="mt-2"
              :template-id="t.id"
              :athlete-id="athleteId"
              @scheduled="reloadSchedule"
            />
          </div>
        </div>
      </section>

      <!-- Athlete-authored workouts shipped in SB-486 and every plan on the
           account is still the coach's — the capability exists and nobody found
           it. Saying what the group is for is the cheap half of the fix. -->
      <div
        v-if="mine.length === 0"
        class="rounded-2xl border border-dashed border-gray-200 p-6 text-center"
        data-testid="mine-empty"
      >
        <p class="text-sm font-semibold text-gray-700">Made something up at practice?</p>
        <p class="mt-1 text-sm text-gray-500">Build it once and it's here to reuse and print.</p>
      </div>

      <div
        v-if="templates.length === 0"
        class="bg-white rounded-xl border border-gray-100 shadow-sm p-8 text-center text-gray-500"
      >
        <p>No workouts yet.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { Pencil, X } from 'lucide-vue-next'
import { useMyAthlete } from '@/composables/useCoach'
import { useMyWorkouts } from '@/composables/useMyWorkouts'
import { renameSession, useWorkoutSessions } from '@/composables/useWorkoutSessions'
import { useWorkoutSchedule, deleteSchedule } from '@/composables/useWorkoutSchedule'
import {
  describeRecurrence,
  stopRecurrence,
  useWorkoutRecurrence,
} from '@/composables/useWorkoutRecurrence'
import { deleteTemplate } from '@/composables/useWorkoutTemplates'
import ScheduleWorkout from '@/components/ScheduleWorkout.vue'
import WorkoutTemplateCard from '@/components/WorkoutTemplateCard.vue'
import { formatDayPill, todayLocalISO } from '@/utils/format'
import { defaultSessionName } from '@/utils/sessionPayload'
import { prettifyKey } from '@/utils/workoutPayload'
import type { WorkoutScheduleEntry, WorkoutTemplate } from '@/types/workout'

const router = useRouter()
const { myAthlete, loadMyAthlete } = useMyAthlete()
const { templates, exercises, loading, error, load } = useMyWorkouts()
const {
  sessions,
  error: sessionsError,
  load: loadSessions,
} = useWorkoutSessions()
const { schedule, load: loadSchedule } = useWorkoutSchedule()
const { recurrences, load: loadRecurrence } = useWorkoutRecurrence()

const tab = ref<'training' | 'plans'>('training')

/**
 * Mine to change (SB-486). A workout the coach prescribed can be logged and
 * printed but not edited — the API enforces that too, this only keeps the
 * buttons honest.
 *
 * Compared against the athlete's own `linked_user_id` rather than the auth
 * store: it is the same user id, already loaded here, and keeps this view free
 * of a Pinia dependency it otherwise would not need.
 */
const isMine = (t: WorkoutTemplate): boolean =>
  !!t.created_by && t.created_by === myAthlete.value?.linked_user_id

/** The athlete this screen is about — read once rather than reached through
 *  `myAthlete` in the template, which relies on ref unwrapping. */
const athleteId = computed(() => myAthlete.value?.id ?? null)

const mine = computed(() => templates.value.filter(isMine))
const fromCoach = computed(() => templates.value.filter((t) => !isMine(t)))

/**
 * "From Matthew" when the plans agree on who wrote them, "From my coach" when
 * they do not. Authorship is the thing worth showing — it is what makes "Mine"
 * feel legitimate rather than odd — and `source` already carries the name.
 */
const coachGroupLabel = computed(() => {
  const names = new Set(fromCoach.value.map((t) => t.source).filter(Boolean))
  return names.size === 1 ? `From ${[...names][0]}` : 'From my coach'
})

const planSummary = (t: WorkoutTemplate): string => {
  const n = t.items?.length ?? 0
  return `${t.type} · ${n} ${n === 1 ? 'exercise' : 'exercises'}`
}

// ---- Coming up -----------------------------------------------------------

/** A plan on a day, with the plan resolved and the author already read. */
interface Occasion {
  id: string
  template: WorkoutTemplate
  scheduled_for: string
  by: string
  mine: boolean
}

const templatesById = computed<Record<string, WorkoutTemplate>>(() => {
  const map: Record<string, WorkoutTemplate> = {}
  for (const t of templates.value) map[t.id] = t
  return map
})

/**
 * Scheduled work, soonest first (SB-534).
 *
 * Read from occasions rather than `workout_templates.scheduled_for`: a plan is
 * reused and an occasion happens once, so the same workout can sit on two days
 * — and only a row can record who put it there.
 *
 * An occasion whose template has since been deleted is dropped rather than
 * rendered as a blank card.
 */
const upcoming = computed<Occasion[]>(() => {
  const today = todayLocalISO()
  const linked = myAthlete.value?.linked_user_id
  return schedule.value
    .filter((s) => s.scheduled_for >= today && templatesById.value[s.template_id])
    .sort((a, b) => (a.scheduled_for < b.scheduled_for ? -1 : 1))
    .map((s) => {
      const mine = !!s.created_by && s.created_by === linked
      return {
        id: s.id,
        template: templatesById.value[s.template_id],
        scheduled_for: s.scheduled_for,
        // Same words as the Plans grouping — one vocabulary, not two.
        by: mine ? 'Mine' : coachGroupLabel.value,
        mine,
      }
    })
})
const dueToday = computed(() => {
  const today = todayLocalISO()
  return upcoming.value.find((o) => o.scheduled_for === today) ?? null
})
/** Everything still ahead once the due one has been promoted to the Start card. */
const laterUp = computed(() => upcoming.value.filter((o) => o.id !== dueToday.value?.id))
const nextUp = computed(() => laterUp.value[0] ?? null)

const reloadSchedule = async (): Promise<void> => {
  if (!myAthlete.value) return
  // Both: a new pattern generates occasions, so the schedule changed too.
  await Promise.all([
    loadSchedule(myAthlete.value.id, todayLocalISO()),
    loadRecurrence(myAthlete.value.id),
  ])
}

/** The live pattern for a plan, if it has one (SB-535). */
const repeatFor = (templateId: string) =>
  recurrences.value.find((r) => r.template_id === templateId && r.active) ?? null

const describeRepeat = describeRecurrence

const stopRepeat = async (recurrenceId: string): Promise<void> => {
  if (!myAthlete.value) return
  // Turning it off stops future occasions and leaves the ones already on the
  // calendar — and anything logged against them — alone.
  await stopRecurrence(recurrenceId, myAthlete.value.id)
  await reloadSchedule()
}

const unschedule = async (o: Occasion): Promise<void> => {
  if (!myAthlete.value) return
  await deleteSchedule(o.id, myAthlete.value.id)
  await reloadSchedule()
}

// ---- Completed -----------------------------------------------------------
const COMPLETED_PREVIEW = 4
const showAllCompleted = ref(false)

const templateNames = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  for (const t of templates.value) map[t.id] = t.name
  return map
})

interface CompletedRow {
  id: string
  title: string
  detail: string
  when: string
  // Only a session with no plan behind it is the athlete's to name (SB-536).
  adhoc: boolean
}

/**
 * What has actually been done, newest first — the half of the loop that had
 * never been shown. The count in the heading is the reward, so it stays
 * truthful: at zero it says so rather than hiding the section.
 *
 * A session with no plan behind it is marked "my own" and otherwise looks
 * exactly like the coach's — noted, not demoted.
 */
const completed = computed<CompletedRow[]>(() =>
  [...sessions.value]
    .sort((a, b) => (a.session_date < b.session_date ? 1 : -1))
    .map((s) => {
      const adhoc = !s.template_id
      const name = s.template_id ? templateNames.value[s.template_id] : null
      const count = s.exercise_count ?? s.sets?.length ?? 0
      const logged = count > 0 ? `${count} ${count === 1 ? 'exercise' : 'exercises'}` : null
      return {
        id: s.id,
        // What he called it, then the plan's name, then the kind of workout it
        // was. The last is the honest fallback for sessions logged before
        // naming existed (SB-536).
        title: s.name?.trim() || name || prettifyKey(s.type),
        adhoc,
        detail: adhoc
          ? [logged, 'my own'].filter(Boolean).join(' · ')
          : logged
            ? `${logged} logged`
            : 'Logged',
        when: formatDayPill(s.session_date),
      }
    }),
)

const visibleCompleted = computed(() =>
  showAllCompleted.value ? completed.value : completed.value.slice(0, COMPLETED_PREVIEW),
)

const thisWeekCount = computed(() => {
  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - 7)
  const since = cutoff.toISOString().slice(0, 10)
  return sessions.value.filter((s) => s.session_date > since).length
})

// ---- Renaming -----------------------------------------------------------
const renamingId = ref<string | null>(null)
const renameText = ref('')

const startRename = (row: CompletedRow): void => {
  renamingId.value = row.id
  renameText.value = row.title
}

/**
 * Save the new name, or fall back to the date-derived default when it is
 * cleared — an empty label on the Completed list would read as nothing.
 */
const saveRename = async (row: CompletedRow): Promise<void> => {
  if (!myAthlete.value) return
  const session = sessions.value.find((s) => s.id === row.id)
  const next =
    renameText.value.trim() || defaultSessionName(session?.session_date ?? todayLocalISO())
  renamingId.value = null
  await renameSession(row.id, next, myAthlete.value.id)
  if (session) session.name = next
}

const remove = async (t: WorkoutTemplate): Promise<void> => {
  if (!myAthlete.value) return
  if (!window.confirm(`Delete "${t.name}"?`)) return
  await deleteTemplate(t.id, myAthlete.value.id)
  await load()
}

onMounted(async () => {
  await loadMyAthlete(true)
  // Not a linked athlete → no workouts to show here.
  if (!myAthlete.value) {
    router.replace('/dashboard')
    return
  }
  // Sessions and the schedule load alongside the plans, not on tab switch:
  // Coming up and Completed are what the Training tab shows, and it is the
  // default tab. Only occasions from today forward — the past is Completed's
  // job, and an unmet Thursday lingering is a decision nobody has made.
  await Promise.all([
    load(),
    loadSessions(myAthlete.value.id),
    loadSchedule(myAthlete.value.id, todayLocalISO()),
    loadRecurrence(myAthlete.value.id),
  ])
})
</script>

<style scoped>
.tab {
  @apply pb-2 text-sm font-semibold text-gray-400 border-b-2 border-transparent -mb-px;
}
.tab-on {
  @apply text-gray-900 border-brand-500;
}
.group-label {
  @apply mb-2 flex items-baseline justify-between text-xs font-bold uppercase tracking-wider text-gray-400;
}
</style>
