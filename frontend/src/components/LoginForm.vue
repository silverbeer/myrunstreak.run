<template>
  <div class="w-full max-w-sm mx-auto">
    <div class="text-center mb-8">
      <BrandLogo :size="72" class="mx-auto" />
      <p class="mt-2 text-sm text-gray-500">
        {{ mode === 'forgot' ? 'Reset your password' : 'Sign in to your account' }}
      </p>
    </div>

    <!-- Login -->
    <form v-if="mode === 'login'" @submit.prevent="handleSignIn" class="space-y-4">
      <div>
        <label for="email" class="form-label">Email</label>
        <input id="email" v-model="email" type="email" required autocomplete="email"
          class="form-input" placeholder="you@example.com" :disabled="auth.loading" />
      </div>
      <div>
        <label for="password" class="form-label">Password</label>
        <input id="password" v-model="password" type="password" required autocomplete="current-password"
          class="form-input" placeholder="••••••••" :disabled="auth.loading" />
      </div>

      <div v-if="auth.error" class="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
        {{ auth.error }}
      </div>

      <button type="submit" class="btn-primary w-full py-2.5" :disabled="auth.loading">
        {{ auth.loading ? 'Signing in…' : 'Sign in' }}
      </button>

      <div class="relative my-2">
        <div class="absolute inset-0 flex items-center"><div class="w-full border-t border-gray-200" /></div>
        <div class="relative flex justify-center"><span class="bg-white px-3 text-xs text-gray-400">or</span></div>
      </div>

      <button type="button" @click="handleGoogleSignIn" :disabled="auth.loading"
        class="w-full flex items-center justify-center gap-3 px-4 py-2.5 border border-gray-300 rounded-lg bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 transition disabled:opacity-50">
        <svg class="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24">
          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
        </svg>
        Continue with Google
      </button>
    </form>

    <!-- Forgot password -->
    <form v-else-if="mode === 'forgot'" @submit.prevent="handleForgotPassword" class="space-y-4">
      <div>
        <label for="forgot-email" class="form-label">Email</label>
        <input id="forgot-email" v-model="email" type="email" required autocomplete="email"
          class="form-input" placeholder="you@example.com" :disabled="auth.loading" />
      </div>

      <div v-if="auth.error" class="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
        {{ auth.error }}
      </div>
      <div v-if="resetSent" class="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-3 py-2">
        Password reset email sent — check your inbox.
      </div>

      <button type="submit" class="btn-primary w-full py-2.5" :disabled="auth.loading || resetSent">
        {{ auth.loading ? 'Sending…' : 'Send reset link' }}
      </button>
    </form>

    <!-- Footer links -->
    <div class="mt-6 text-center text-sm text-gray-500 space-y-2">
      <template v-if="mode === 'login'">
        <p>
          <button @click="switchMode('forgot')" class="text-brand-600 hover:underline font-medium">Forgot password?</button>
        </p>
        <p class="text-xs text-gray-400">
          MyRunStreak is invite-only. Got an invite link? It'll bring you straight to sign-up.
        </p>
      </template>
      <template v-else>
        <p>
          <button @click="switchMode('login')" class="text-brand-600 hover:underline font-medium">← Back to sign in</button>
        </p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import BrandLogo from '@/components/BrandLogo.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

type Mode = 'login' | 'forgot'
const mode = ref<Mode>('login')
const email = ref('')
const password = ref('')
const resetSent = ref(false)

const switchMode = (next: Mode) => {
  mode.value = next
  auth.clearError()
  resetSent.value = false
}

const handleSignIn = async () => {
  const result = await auth.signIn(email.value, password.value)
  if (result.success) {
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  }
}

const handleGoogleSignIn = async () => {
  await auth.signInWithGoogle()
}

const handleForgotPassword = async () => {
  const result = await auth.requestPasswordReset(email.value)
  if (result.success) {
    resetSent.value = true
  }
}
</script>
