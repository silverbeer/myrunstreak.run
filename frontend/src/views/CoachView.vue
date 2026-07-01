<template>
  <div class="container-app py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Athletes</h1>
        <p class="text-sm text-gray-500 mt-1">
          {{ athletes.length > 0 ? `Coaching ${athletes.length}` : 'No athletes yet' }}
        </p>
      </div>
      <button class="btn-primary text-sm" @click="showForm = !showForm">
        {{ showForm ? 'Cancel' : '+ Add athlete' }}
      </button>
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

    <div v-if="loading && athletes.length === 0" class="space-y-2">
      <div v-for="i in 3" :key="i" class="bg-white rounded-lg border border-gray-100 h-16 animate-pulse" />
    </div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
      {{ error }}
    </div>

    <div
      v-else-if="athletes.length === 0"
      class="bg-white rounded-xl border border-gray-100 shadow-sm p-10 text-center text-gray-500"
    >
      <p>No athletes yet. Click <span class="font-semibold">Add athlete</span> to create one.</p>
    </div>

    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <RouterLink
        v-for="a in athletes"
        :key="a.id"
        :to="`/coach/${a.id}`"
        class="bg-white rounded-xl border border-gray-100 shadow-sm p-4 hover:border-brand-300 hover:shadow transition"
      >
        <p class="font-semibold text-gray-900">{{ a.display_name }}</p>
        <p class="text-sm text-gray-500 mt-1">
          {{ a.birth_year ? `Born ${a.birth_year}` : 'No birth year' }}
          <span v-if="a.linked_user_id" class="text-brand-600"> · has login</span>
        </p>
      </RouterLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useCoach } from '@/composables/useCoach'
import type { AthleteCreate } from '@/types/coach'

const { athletes, loading, error, loadAthletes, createAthlete } = useCoach()

const showForm = ref(false)
const saving = ref(false)
const form = reactive<AthleteCreate>({ display_name: '', birth_year: null, notes: null })

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
  }
}

onMounted(loadAthletes)
</script>
