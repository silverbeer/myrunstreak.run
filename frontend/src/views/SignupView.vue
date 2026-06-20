<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 to-white px-4">
    <div class="w-full max-w-sm mx-auto">
      <div class="text-center mb-8">
        <span class="text-5xl">🏃</span>
        <h1 class="mt-3 text-2xl font-bold text-gray-900">MyRunStreak</h1>
        <p class="mt-1 text-sm text-gray-500">Invite-only — claim your account</p>
      </div>

      <!-- No invite token in the link -->
      <div v-if="!token" class="text-center space-y-4">
        <div class="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg px-4 py-3">
          MyRunStreak is currently invite-only. You need an invite link to create an account.
        </div>
        <p class="text-sm text-gray-500">
          Already have an account?
          <router-link to="/login" class="text-brand-600 hover:underline font-medium">Sign in</router-link>
        </p>
      </div>

      <!-- Redeem form -->
      <form v-else @submit.prevent="handleRedeem" class="space-y-4">
        <div>
          <label for="password" class="form-label">Choose a password</label>
          <input id="password" v-model="password" type="password" required autocomplete="new-password"
            class="form-input" placeholder="••••••••" minlength="6" :disabled="auth.loading" />
        </div>
        <div>
          <label for="confirm" class="form-label">Confirm password</label>
          <input id="confirm" v-model="confirm" type="password" required autocomplete="new-password"
            class="form-input" placeholder="••••••••" minlength="6" :disabled="auth.loading" />
        </div>

        <div v-if="mismatch" class="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
          Passwords don't match.
        </div>
        <div v-if="auth.error" class="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
          {{ auth.error }}
        </div>

        <button type="submit" class="btn-primary w-full py-2.5" :disabled="auth.loading">
          {{ auth.loading ? 'Creating account…' : 'Create account' }}
        </button>

        <p class="text-center text-sm text-gray-500">
          Already have an account?
          <router-link to="/login" class="text-brand-600 hover:underline font-medium">Sign in</router-link>
        </p>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const token = (route.query.invite as string) || ''
const password = ref('')
const confirm = ref('')

const mismatch = computed(() => confirm.value.length > 0 && password.value !== confirm.value)

const handleRedeem = async () => {
  if (password.value !== confirm.value) return
  const result = await auth.redeemInvite(token, password.value)
  if (result.success) router.push('/dashboard')
}
</script>
