<template>
  <div class="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-6">
    <h2 class="text-sm font-semibold uppercase tracking-wide text-gray-400">Access</h2>

    <!-- Invite the athlete to their own login (only if not linked yet) -->
    <div v-if="!athlete.linked_user_id" class="space-y-2">
      <p class="text-sm font-medium text-gray-700">Invite {{ athlete.display_name }} to log in</p>
      <form class="flex flex-wrap items-center gap-2" @submit.prevent="doInvite">
        <input
          v-model="inviteEmail"
          type="email"
          required
          placeholder="athlete's email"
          class="form-input flex-1 min-w-48"
        />
        <button type="submit" :disabled="inviting" class="btn-primary text-sm">
          {{ inviting ? 'Inviting…' : 'Invite athlete' }}
        </button>
      </form>
      <div v-if="inviteLink" class="text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded-lg p-3">
        <p class="mb-1 font-medium text-gray-700">Send this link:</p>
        <div class="flex items-center gap-2">
          <code class="flex-1 break-all">{{ inviteLink }}</code>
          <button type="button" class="btn-secondary text-xs" @click="copy(inviteLink)">
            {{ copied ? 'Copied' : 'Copy' }}
          </button>
        </div>
      </div>
    </div>
    <p v-else class="text-sm text-gray-500">
      {{ athlete.display_name }} has their own login. ✓
    </p>

    <!-- Add an existing user as a coach -->
    <div class="space-y-2 border-t border-gray-100 pt-5">
      <p class="text-sm font-medium text-gray-700">Add a coach</p>
      <form class="flex flex-wrap items-center gap-2" @submit.prevent="doAddCoach">
        <input
          v-model="coachEmail"
          type="email"
          required
          placeholder="coach's email"
          class="form-input flex-1 min-w-48"
        />
        <button type="submit" :disabled="addingCoach" class="btn-secondary text-sm">
          {{ addingCoach ? 'Adding…' : 'Add coach' }}
        </button>
      </form>
      <p class="text-xs text-gray-400">
        The coach must already have an account — invite them with a coach role first
        (<code>stk invite create --role coach</code>).
      </p>
    </div>

    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
      {{ error }}
    </div>
    <div v-if="success" class="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-3 py-2">
      {{ success }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { addCoachByEmail, inviteAthlete } from '@/composables/useCoach'
import type { Athlete } from '@/types/coach'

const props = defineProps<{ athlete: Athlete }>()

const inviteEmail = ref('')
const inviting = ref(false)
const inviteLink = ref('')
const copied = ref(false)

const coachEmail = ref('')
const addingCoach = ref(false)

const error = ref<string | null>(null)
const success = ref<string | null>(null)

const copy = async (text: string) => {
  await navigator.clipboard?.writeText(text)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}

const doInvite = async () => {
  inviting.value = true
  error.value = null
  success.value = null
  inviteLink.value = ''
  try {
    const { token } = await inviteAthlete(inviteEmail.value, props.athlete.id)
    inviteLink.value = `${window.location.origin}/signup?invite=${token}`
    success.value = 'Invite created — copy the link below.'
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to create invite'
  } finally {
    inviting.value = false
  }
}

const doAddCoach = async () => {
  addingCoach.value = true
  error.value = null
  success.value = null
  try {
    await addCoachByEmail(props.athlete.id, coachEmail.value)
    success.value = `Added ${coachEmail.value} as a coach.`
    coachEmail.value = ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to add coach'
  } finally {
    addingCoach.value = false
  }
}
</script>
