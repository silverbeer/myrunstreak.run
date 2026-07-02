<template>
  <div class="container-app py-8 max-w-2xl">
    <h1 class="text-2xl font-bold text-gray-900 mb-1">My profile</h1>
    <p class="text-sm text-gray-500 mb-6">Update your bio, goals, and contact details.</p>

    <div v-if="loading" class="space-y-3">
      <div v-for="i in 4" :key="i" class="h-10 bg-white rounded-lg border border-gray-100 animate-pulse" />
    </div>

    <div
      v-else-if="!myAthlete"
      class="bg-white rounded-xl border border-gray-100 shadow-sm p-8 text-center text-gray-500"
    >
      <p>No athlete profile is linked to your account.</p>
    </div>

    <div v-else class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
      <p class="text-lg font-semibold text-gray-900 mb-4">{{ myAthlete.display_name }}</p>
      <AthleteProfileForm :athlete="myAthlete" mode="athlete" @saved="onSaved" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMyAthlete } from '@/composables/useCoach'
import AthleteProfileForm from '@/components/AthleteProfileForm.vue'
import type { Athlete } from '@/types/coach'

const router = useRouter()
const { myAthlete, loadMyAthlete } = useMyAthlete()
const loading = ref(true)

const onSaved = (updated: Athlete) => {
  myAthlete.value = updated
}

onMounted(async () => {
  await loadMyAthlete(true)
  loading.value = false
  // Not a linked athlete → nothing to edit here.
  if (!myAthlete.value) router.replace('/dashboard')
})
</script>
