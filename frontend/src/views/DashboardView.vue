<template>
  <div class="container-app py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Dashboard</h1>
      <p class="text-gray-500 text-sm mt-1">Welcome back, {{ userEmail }}</p>
    </div>

    <!-- Streak card placeholder -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
      <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Current Streak</p>
        <p class="mt-2 text-4xl font-bold text-brand-600">–</p>
        <p class="text-sm text-gray-500 mt-1">days</p>
      </div>
      <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Longest Streak</p>
        <p class="mt-2 text-4xl font-bold text-gray-700">–</p>
        <p class="text-sm text-gray-500 mt-1">days</p>
      </div>
      <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Total Runs</p>
        <p class="mt-2 text-4xl font-bold text-gray-700">–</p>
        <p class="text-sm text-gray-500 mt-1">all time</p>
      </div>
    </div>

    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6 text-center text-gray-400">
      <p class="text-4xl mb-3">🏗️</p>
      <p class="font-medium">Run data coming soon</p>
      <p class="text-sm mt-1">Stats and history will appear here once the API is wired up.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const userEmail = computed(() => auth.user?.email ?? 'runner')
</script>
