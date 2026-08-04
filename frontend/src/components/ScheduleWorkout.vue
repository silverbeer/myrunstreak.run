<template>
  <div>
    <button
      v-if="!open"
      type="button"
      class="w-full rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
      data-testid="schedule-open"
      @click="open = true"
    >
      Schedule for a day
    </button>

    <div v-else class="rounded-lg border border-gray-200 p-3" data-testid="schedule-form">
      <!-- One control, two shapes. A week that repeats is the same act as a
           single day — putting it behind a separate screen would make the
           common case (Matthew's in-season week) the hidden one (SB-535). -->
      <div class="mb-2 flex gap-1 text-xs">
        <button
          type="button"
          class="mode"
          :class="repeat ? 'mode-off' : 'mode-on'"
          data-testid="mode-once"
          @click="repeat = false"
        >
          Once
        </button>
        <button
          type="button"
          class="mode"
          :class="repeat ? 'mode-on' : 'mode-off'"
          data-testid="mode-repeat"
          @click="repeat = true"
        >
          Every week
        </button>
      </div>

      <label class="block text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">
        {{ repeat ? 'Starting' : 'Put this on a day' }}
      </label>
      <input
        v-model="day"
        type="date"
        :min="today"
        class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
        data-testid="schedule-date"
      />

      <div v-if="repeat" class="mt-2" data-testid="weekday-chips">
        <span class="block text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">
          On these days
        </span>
        <div class="flex gap-1">
          <button
            v-for="d in WEEKDAY_CHIPS"
            :key="d.value"
            type="button"
            class="chip"
            :class="days.includes(d.value) ? 'chip-on' : 'chip-off'"
            :aria-pressed="days.includes(d.value)"
            :data-testid="`weekday-${d.value}`"
            @click="toggleDay(d.value)"
          >
            {{ d.label }}
          </button>
        </div>
      </div>

      <p v-if="error" class="mt-2 text-sm text-red-600" data-testid="schedule-error">{{ error }}</p>
      <div class="mt-2 flex gap-2">
        <button
          type="button"
          class="flex-1 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          :disabled="!canSave || saving"
          data-testid="schedule-save"
          @click="save"
        >
          {{ saving ? 'Scheduling…' : repeat ? 'Repeat weekly' : 'Schedule' }}
        </button>
        <button
          type="button"
          class="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
          data-testid="schedule-cancel"
          @click="close"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { createSchedule } from '@/composables/useWorkoutSchedule'
import { WEEKDAY_CHIPS, createRecurrence } from '@/composables/useWorkoutRecurrence'
import { todayLocalISO } from '@/utils/format'

/**
 * Put a plan on a day, once or every week (SB-534, SB-535).
 *
 * One component for both surfaces on purpose: the coach schedules from the
 * athlete's detail view and the athlete from their own Plans tab, and the API
 * authorises them identically. Two copies of this would drift, which is exactly
 * how the athlete-side bugs of the last week happened.
 */
// athleteId null = scheduling my own workout (SB-578); the API reads the
// caller's self-owned rows when no act-as header is sent.
const props = defineProps<{ templateId: string; athleteId: string | null }>()
const emit = defineEmits<{ (e: 'scheduled'): void }>()

const open = ref(false)
const repeat = ref(false)
const day = ref('')
const days = ref<number[]>([])
const saving = ref(false)
const error = ref<string | null>(null)
const today = todayLocalISO()

const toggleDay = (d: number): void => {
  days.value = days.value.includes(d) ? days.value.filter((x) => x !== d) : [...days.value, d]
}

/** A repeat with no days picked would silently never fire. */
const canSave = computed(() => !!day.value && (!repeat.value || days.value.length > 0))

const close = (): void => {
  open.value = false
  repeat.value = false
  day.value = ''
  days.value = []
  error.value = null
}

const save = async (): Promise<void> => {
  if (!canSave.value) return
  saving.value = true
  error.value = null
  try {
    if (repeat.value) {
      await createRecurrence(
        { template_id: props.templateId, byweekday: days.value, starts_on: day.value },
        props.athleteId,
      )
    } else {
      await createSchedule(
        { template_id: props.templateId, scheduled_for: day.value },
        props.athleteId,
      )
    }
    close()
    emit('scheduled')
  } catch (e) {
    // The unique index rejects the same plan on the same day twice; say so
    // rather than showing a raw constraint error.
    const message = e instanceof Error ? e.message : 'Could not schedule it'
    error.value = /duplicate|unique/i.test(message)
      ? "That's already on the calendar for this day."
      : message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.mode {
  @apply rounded-lg px-2.5 py-1 font-semibold;
}
.mode-on {
  @apply bg-brand-600 text-white;
}
.mode-off {
  @apply border border-gray-200 text-gray-600;
}
.chip {
  @apply h-8 w-8 rounded-full text-xs font-semibold;
}
.chip-on {
  @apply bg-brand-600 text-white;
}
.chip-off {
  @apply border border-gray-200 text-gray-600;
}
</style>
