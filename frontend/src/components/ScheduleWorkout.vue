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
      <label class="block text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">
        Put this on a day
      </label>
      <input
        v-model="day"
        type="date"
        :min="today"
        class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
        data-testid="schedule-date"
      />
      <p v-if="error" class="mt-2 text-sm text-red-600" data-testid="schedule-error">{{ error }}</p>
      <div class="mt-2 flex gap-2">
        <button
          type="button"
          class="flex-1 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          :disabled="!day || saving"
          data-testid="schedule-save"
          @click="save"
        >
          {{ saving ? 'Scheduling…' : 'Schedule' }}
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
import { ref } from 'vue'
import { createSchedule } from '@/composables/useWorkoutSchedule'
import { todayLocalISO } from '@/utils/format'

/**
 * Put a plan on a day (SB-534).
 *
 * One component for both surfaces on purpose: the coach schedules from the
 * athlete's detail view and the athlete from their own Plans tab, and the API
 * authorises them identically. Two copies of this would drift, which is exactly
 * how the athlete-side bugs of the last week happened.
 */
const props = defineProps<{ templateId: string; athleteId: string }>()
const emit = defineEmits<{ (e: 'scheduled'): void }>()

const open = ref(false)
const day = ref('')
const saving = ref(false)
const error = ref<string | null>(null)
const today = todayLocalISO()

const close = (): void => {
  open.value = false
  day.value = ''
  error.value = null
}

const save = async (): Promise<void> => {
  if (!day.value) return
  saving.value = true
  error.value = null
  try {
    await createSchedule({ template_id: props.templateId, scheduled_for: day.value }, props.athleteId)
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
