<template>
  <div class="container-app py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Coach</h1>
        <p class="text-sm text-gray-500 mt-1">
          {{ cards.length > 0 ? `Coaching ${cards.length}` : 'No athletes yet' }}
          <span v-if="home && home.pending_invites > 0" class="text-amber-600">
            · {{ home.pending_invites }} pending invite{{ home.pending_invites > 1 ? 's' : '' }}
          </span>
        </p>
      </div>
      <div class="flex gap-2">
        <RouterLink to="/exercises" class="btn-secondary text-sm">Exercise catalog</RouterLink>
        <button class="btn-primary text-sm" @click="showForm = !showForm">
          {{ showForm ? 'Cancel' : '+ Add athlete' }}
        </button>
      </div>
    </div>

    <form
      v-if="showForm"
      class="bg-white rounded-xl border border-gray-100 shadow-sm p-4 mb-6 space-y-3"
      @submit.prevent="submit"
    >
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <input
          v-model="form.display_name"
          required
          placeholder="Name"
          class="border border-gray-200 rounded-lg px-3 py-2 text-sm sm:col-span-2"
        />
        <input
          v-model.number="form.birth_year"
          type="number"
          placeholder="Birth year"
          class="border border-gray-200 rounded-lg px-3 py-2 text-sm"
        />
      </div>
      <input
        v-model="form.notes"
        placeholder="Notes (optional)"
        class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
      />
      <button type="submit" :disabled="saving" class="btn-primary text-sm">
        {{ saving ? 'Saving…' : 'Create athlete' }}
      </button>
    </form>

    <div v-if="loading && !home" class="space-y-2">
      <div v-for="i in 3" :key="i" class="bg-white rounded-lg border border-gray-100 h-24 animate-pulse" />
    </div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
      {{ error }}
    </div>

    <template v-else>
      <div
        v-if="cards.length === 0"
        class="bg-white rounded-xl border border-gray-100 shadow-sm p-10 text-center text-gray-500"
      >
        <p>No athletes yet. Click <span class="font-semibold">Add athlete</span> to create one.</p>
      </div>

      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <RouterLink
          v-for="c in cards"
          :key="c.athlete.id"
          :to="`/coach/${c.athlete.id}`"
          class="bg-white rounded-xl border shadow-sm p-4 hover:shadow transition"
          :class="c.needs_attention ? 'border-amber-300 hover:border-amber-400' : 'border-gray-100 hover:border-brand-300'"
        >
          <div class="flex items-start justify-between">
            <p class="font-semibold text-gray-900">{{ c.athlete.display_name }}</p>
            <span
              v-if="c.needs_attention"
              class="text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5"
            >
              workout waiting
            </span>
          </div>
          <p class="text-sm text-gray-500 mt-2">
            {{ c.last_session_date ? `Last logged ${formatDay(c.last_session_date)}` : 'Nothing logged yet' }}
            <span v-if="c.sessions_count"> · {{ c.sessions_count }} session{{ c.sessions_count > 1 ? 's' : '' }}</span>
          </p>
          <p v-if="c.latest_template_name" class="text-sm text-gray-500 mt-1 truncate">
            Plan: <span class="text-gray-700">{{ c.latest_template_name }}</span>
          </p>
        </RouterLink>
      </div>

      <div v-if="home && home.recent_sessions.length > 0">
        <h2 class="text-lg font-semibold text-gray-900 mb-3">Recent activity</h2>
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm divide-y divide-gray-50">
          <RouterLink
            v-for="s in home.recent_sessions"
            :key="s.id"
            :to="`/coach/${s.athlete_id}`"
            class="flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition"
          >
            <div class="min-w-0">
              <p class="text-sm font-medium text-gray-900">
                {{ s.athlete_name }}
                <span class="text-gray-400 font-normal"> · {{ s.template_name || s.type }}</span>
              </p>
              <p v-if="s.how_felt" class="text-xs text-gray-500 truncate mt-0.5">{{ s.how_felt }}</p>
            </div>
            <span class="text-sm text-gray-500 shrink-0 ml-4">{{ formatDay(s.session_date) }}</span>
          </RouterLink>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useCoach } from '@/composables/useCoach'
import { useCoachHome } from '@/composables/useCoachHome'
import type { AthleteCreate } from '@/types/coach'

const { createAthlete } = useCoach()
const { home, loading, error, load } = useCoachHome()

const cards = computed(() => home.value?.athletes ?? [])

const showForm = ref(false)
const saving = ref(false)
const form = reactive<AthleteCreate>({ display_name: '', birth_year: null, notes: null })

const formatDay = (iso: string): string => {
  const d = new Date(`${iso}T00:00:00`)
  const today = new Date()
  const days = Math.round((today.setHours(0, 0, 0, 0) - d.getTime()) / 86_400_000)
  if (days === 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 7) return d.toLocaleDateString(undefined, { weekday: 'short' })
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

const submit = async () => {
  saving.value = true
  const created = await createAthlete({
    display_name: form.display_name,
    birth_year: form.birth_year || null,
    notes: form.notes || null,
  })
  saving.value = false
  if (created) {
    form.display_name = ''
    form.birth_year = null
    form.notes = null
    showForm.value = false
    await load()
  }
}

onMounted(load)
</script>
