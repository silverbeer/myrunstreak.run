<template>
  <form class="space-y-6" @submit.prevent="submit">
    <!-- Sport (coach only) -->
    <fieldset v-if="mode === 'coach'" class="space-y-3">
      <legend class="text-sm font-semibold text-gray-700 mb-1">Sport</legend>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div><label class="form-label">Sport</label><input v-model="f.sport" class="form-input" /></div>
        <div><label class="form-label">Position</label><input v-model="f.position" class="form-input" /></div>
        <div><label class="form-label">Team</label><input v-model="f.team" class="form-input" /></div>
        <div>
          <label class="form-label">Dominant side</label>
          <select v-model="f.dominant_side" class="form-input">
            <option :value="null">—</option>
            <option value="left">Left</option>
            <option value="right">Right</option>
            <option value="both">Both</option>
          </select>
        </div>
        <div><label class="form-label">Jersey #</label><input v-model="f.jersey_number" class="form-input" /></div>
      </div>
    </fieldset>

    <!-- Physical (coach only) -->
    <fieldset v-if="mode === 'coach'" class="space-y-3">
      <legend class="text-sm font-semibold text-gray-700 mb-1">Physical</legend>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div><label class="form-label">Height (cm)</label><input v-model.number="f.height_cm" type="number" class="form-input" /></div>
        <div><label class="form-label">Weight (kg)</label><input v-model.number="f.weight_kg" type="number" class="form-input" /></div>
        <div><label class="form-label">Date of birth</label><input v-model="f.date_of_birth" type="date" class="form-input" /></div>
        <div>
          <label class="form-label">Sex</label>
          <select v-model="f.sex" class="form-input">
            <option :value="null">—</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>
    </fieldset>

    <!-- About (athlete-editable) -->
    <fieldset class="space-y-3">
      <legend class="text-sm font-semibold text-gray-700 mb-1">About</legend>
      <div><label class="form-label">Bio</label><textarea v-model="f.bio" rows="3" class="form-input" /></div>
      <div><label class="form-label">Personal goals</label><textarea v-model="f.personal_goals" rows="2" class="form-input" /></div>
    </fieldset>

    <!-- Contact & guardian (athlete-editable) -->
    <fieldset class="space-y-3">
      <legend class="text-sm font-semibold text-gray-700 mb-1">Contact &amp; guardian</legend>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div><label class="form-label">Email</label><input v-model="f.athlete_email" type="email" class="form-input" /></div>
        <div><label class="form-label">Phone</label><input v-model="f.athlete_phone" class="form-input" /></div>
        <div><label class="form-label">Guardian name</label><input v-model="f.guardian_name" class="form-input" /></div>
        <div><label class="form-label">Guardian email</label><input v-model="f.guardian_email" type="email" class="form-input" /></div>
        <div><label class="form-label">Guardian phone</label><input v-model="f.guardian_phone" class="form-input" /></div>
      </div>
    </fieldset>

    <!-- Coaching notes (coach only, private) -->
    <fieldset v-if="mode === 'coach'" class="space-y-3">
      <legend class="text-sm font-semibold text-gray-700 mb-1">
        Coaching notes <span class="font-normal text-gray-400">· private (athlete can't see)</span>
      </legend>
      <textarea v-model="f.coaching_notes" rows="3" class="form-input" />
    </fieldset>

    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
      {{ error }}
    </div>
    <div v-if="saved" class="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-3 py-2">
      Saved.
    </div>

    <button type="submit" :disabled="saving" class="btn-primary text-sm">
      {{ saving ? 'Saving…' : 'Save profile' }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { updateAthleteProfile } from '@/composables/useCoach'
import type { Athlete, AthleteProfile, AthleteProfileUpdate } from '@/types/coach'

const props = defineProps<{ athlete: Athlete; mode: 'coach' | 'athlete' }>()
const emit = defineEmits<{ saved: [Athlete] }>()

// Which keys each mode may send (mirrors the server allowlist).
const ATHLETE_FIELDS = [
  'bio', 'personal_goals', 'athlete_email', 'athlete_phone',
  'guardian_name', 'guardian_email', 'guardian_phone',
] as const
const COACH_FIELDS = [
  'sport', 'position', 'team', 'dominant_side', 'jersey_number',
  'height_cm', 'weight_kg', 'date_of_birth', 'sex',
  ...ATHLETE_FIELDS, 'coaching_notes',
] as const

type FormValue = string | number | null
type FormKey = keyof AthleteProfile
const blank = (): Record<FormKey, FormValue> =>
  ({
    sport: null, position: null, team: null, dominant_side: null, jersey_number: null,
    height_cm: null, weight_kg: null, date_of_birth: null, sex: null,
    bio: null, personal_goals: null, athlete_email: null, athlete_phone: null,
    guardian_name: null, guardian_email: null, guardian_phone: null,
    coaching_notes: null, updated_at: null,
  }) as Record<FormKey, FormValue>

const f = reactive<Record<string, FormValue>>(blank())

watch(
  () => props.athlete,
  (a) => Object.assign(f, blank(), a.profile ?? {}),
  { immediate: true },
)

const saving = ref(false)
const saved = ref(false)
const error = ref<string | null>(null)

const submit = async () => {
  saving.value = true
  saved.value = false
  error.value = null
  const keys = props.mode === 'coach' ? COACH_FIELDS : ATHLETE_FIELDS
  const patch: AthleteProfileUpdate = {}
  for (const k of keys) {
    const v = f[k]
    ;(patch as Record<string, unknown>)[k] = v === '' ? null : v
  }
  try {
    const updated = await updateAthleteProfile(props.athlete.id, patch)
    emit('saved', updated)
    saved.value = true
    setTimeout(() => (saved.value = false), 2500)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to save'
  } finally {
    saving.value = false
  }
}
</script>
