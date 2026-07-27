<template>
  <div class="container-app py-12 max-w-md">
    <div class="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h1 class="text-2xl font-bold text-gray-900 mb-1">Reset your password</h1>
      <p class="text-gray-500 text-sm mb-6">Enter a new password below.</p>

      <!-- Verifying the recovery link -->
      <div v-if="status === 'checking'" class="text-sm text-gray-400 py-6 text-center">
        Verifying your reset link…
      </div>

      <!-- Expired / already-used link (incl. Gmail link prefetch consuming the OTP) -->
      <div
        v-else-if="status === 'expired'"
        class="bg-amber-50 border border-amber-200 text-amber-700 text-sm rounded-lg px-3 py-2"
      >
        This reset link has expired or was already used. Request a new one from the
        <RouterLink to="/login" class="underline font-medium">login page</RouterLink>.
      </div>

      <!-- No recovery session at all → bad link / opened directly -->
      <div
        v-else-if="status === 'invalid'"
        class="bg-amber-50 border border-amber-200 text-amber-700 text-sm rounded-lg px-3 py-2"
      >
        This page needs a valid password-reset link. Request one from the
        <RouterLink to="/login" class="underline font-medium">login page</RouterLink>.
      </div>

      <!-- Success -->
      <div
        v-else-if="status === 'success'"
        class="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-3 py-2"
      >
        Password updated. Redirecting to login…
      </div>

      <!-- Form (recovery session present) -->
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

        <button type="submit" class="btn-primary w-full py-2.5" :disabled="auth.loading">
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
import { supabase } from '@/config/supabase'

const auth = useAuthStore()
const router = useRouter()

const newPassword = ref('')
const confirmPassword = ref('')
const localError = ref<string | null>(null)
type Status = 'checking' | 'ready' | 'expired' | 'invalid' | 'success'
const status = ref<Status>('checking')

// Supabase (detectSessionInUrl) processes the recovery link on load: it either
// establishes a short-lived RECOVERY SESSION (→ we can updateUser), or leaves an
// error in the hash (expired/consumed link — e.g. Gmail prefetch used the OTP).
// We read the SESSION, not the access_token from the hash (Supabase strips it).
onMounted(async () => {
  const hash = window.location.hash.replace(/^#/, '')
  const params = new URLSearchParams(hash)
  if (params.get('error') || params.get('error_code')) {
    status.value = 'expired'
    return
  }
  const { data } = await supabase.auth.getSession()
  status.value = data.session ? 'ready' : 'invalid'
})

const formError = computed(() => localError.value ?? auth.error)

const handleSubmit = async () => {
  localError.value = null
  if (newPassword.value !== confirmPassword.value) {
    localError.value = 'Passwords do not match.'
    return
  }
  const result = await auth.updatePassword(newPassword.value)
  if (result.success) {
    status.value = 'success'
    await auth.signOut()
    setTimeout(() => router.push('/login'), 1500)
  }
}
</script>
