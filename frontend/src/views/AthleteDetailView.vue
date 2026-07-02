<template>
  <div class="container-app py-8">
    <RouterLink to="/coach" class="text-sm text-brand-600 hover:text-brand-700">← Athletes</RouterLink>

    <div v-if="loading" class="mt-4 space-y-2">
      <div class="bg-white rounded-lg border border-gray-100 h-20 animate-pulse" />
      <div v-for="i in 4" :key="i" class="bg-white rounded-lg border border-gray-100 h-14 animate-pulse" />
    </div>

    <div v-else-if="error" class="mt-4 bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
      {{ error }}
    </div>

    <template v-else-if="athlete">
      <div class="mt-4 mb-6">
        <h1 class="text-2xl font-bold text-gray-900">{{ athlete.display_name }}</h1>
        <p class="text-sm text-gray-500 mt-1">
          {{ athlete.birth_year ? `Born ${athlete.birth_year}` : 'No birth year' }}
          <span v-if="athlete.linked_user_id" class="text-brand-600"> · has own login</span>
        </p>
        <p v-if="athlete.notes" class="text-sm text-gray-600 mt-2">{{ athlete.notes }}</p>
        <button class="btn-secondary text-sm mt-3" @click="editing = !editing">
          {{ editing ? 'Cancel' : 'Edit profile' }}
        </button>
      </div>

      <div v-if="editing" class="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
        <AthleteProfileForm :athlete="athlete" mode="coach" @saved="onSaved" />
      </div>

      <AthleteAccessPanel :athlete="athlete" class="mb-6" />

      <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">
        Recent sessions ({{ sessions.length }})
      </h2>

      <div
        v-if="sessions.length === 0"
        class="bg-white rounded-xl border border-gray-100 shadow-sm p-8 text-center text-gray-500"
      >
        <p>No workout sessions logged yet.</p>
      </div>

      <div v-else class="bg-white rounded-xl border border-gray-100 shadow-sm divide-y divide-gray-100">
        <div v-for="s in sessions" :key="s.id" class="px-4 py-3 flex items-center justify-between">
          <div>
            <p class="font-medium text-gray-900">{{ s.session_date }}</p>
            <p class="text-xs text-gray-500 mt-0.5 capitalize">
              {{ s.type }}<span v-if="s.how_felt"> · felt {{ s.how_felt }}</span>
            </p>
          </div>
          <div class="text-right text-sm text-gray-600">
            <p>{{ s.sets.length }} {{ s.sets.length === 1 ? 'set' : 'sets' }}</p>
            <p v-if="s.total_minutes" class="text-xs text-gray-400">{{ s.total_minutes }} min</p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useAthleteDetail } from '@/composables/useCoach'
import AthleteProfileForm from '@/components/AthleteProfileForm.vue'
import AthleteAccessPanel from '@/components/AthleteAccessPanel.vue'
import type { Athlete } from '@/types/coach'

const route = useRoute()
const { athlete, sessions, loading, error, load } = useAthleteDetail(route.params.athleteId as string)

const editing = ref(false)
const onSaved = (updated: Athlete) => {
  athlete.value = updated
  editing.value = false
}

onMounted(load)
</script>
