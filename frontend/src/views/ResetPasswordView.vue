<template>
  <div class="container-app py-12 max-w-md">
    <div class="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h1 class="text-2xl font-bold text-gray-900 mb-1">Reset your password</h1>
      <p class="text-gray-500 text-sm mb-6">Enter a new password below.</p>

      <!-- No recovery token in URL → bad/expired link -->
      <div
        v-if="!accessToken"
        class="bg-amber-50 border border-amber-200 text-amber-700 text-sm rounded-lg px-3 py-2"
      >
        This reset link is missing a recovery token. Request a new password reset email
        from the
        <RouterLink to="/login" class="underline font-medium">login page</RouterLink>.
      </div>

      <!-- Success state -->
      <div
        v-else-if="success"
        class="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-3 py-2"
      >
        Password updated. Redirecting to login…
      </div>

      <!-- Form -->
      <form v-else @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label for="new-password" class="form-label">New password</label>
          <input
            id="new-password"
            v-model="newPassword"
            type="password"
            required
            minlength="6"
            autocomplete="new-password"
            class="form-input"
          />
        </div>
        <div>
          <label for="confirm-password" class="form-label">Confirm new password</label>
          <input
            id="confirm-password"
            v-model="confirmPassword"
            type="password"
            required
            minlength="6"
            autocomplete="new-password"
            class="form-input"
          />
        </div>

        <div
          v-if="formError"
          class="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2"
        >
          {{ formError }}
        </div>

        <button
          type="submit"
          class="btn-primary w-full py-2.5"
          :disabled="auth.loading"
        >
          {{ auth.loading ? 'Updating…' : 'Update password' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const newPassword = ref('')
const confirmPassword = ref('')
const success = ref(false)
const localError = ref<string | null>(null)

// Supabase puts the recovery token in the URL fragment (after #), e.g.
//   /auth/reset-password#access_token=...&type=recovery&...
// onMounted reads it once; we don't watch — the user only resets once per
// page load.
const accessToken = ref<string | null>(null)

onMounted(() => {
  const hash = window.location.hash.startsWith('#')
    ? window.location.hash.slice(1)
    : window.location.hash
  const params = new URLSearchParams(hash)
  accessToken.value = params.get('access_token')
})

const formError = computed(() => localError.value ?? auth.error)

const handleSubmit = async () => {
  localError.value = null

  if (newPassword.value !== confirmPassword.value) {
    localError.value = 'Passwords do not match.'
    return
  }
  if (!accessToken.value) {
    localError.value = 'Missing recovery token.'
    return
  }

  const result = await auth.applyPasswordReset(accessToken.value, newPassword.value)
  if (result.success) {
    success.value = true
    setTimeout(() => router.push('/login'), 1500)
  }
}
</script>
