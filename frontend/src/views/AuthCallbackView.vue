<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="text-center">
      <div class="animate-spin w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full mx-auto mb-4"></div>
      <p class="text-gray-500 text-sm">Completing sign in…</p>
      <p v-if="error" class="mt-3 text-red-600 text-sm">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { supabase } from '@/config/supabase'

const router = useRouter()
const error = ref<string | null>(null)

onMounted(async () => {
  // Supabase handles the PKCE/implicit flow from URL hash automatically
  const { data, error: err } = await supabase.auth.getSession()
  if (err) {
    error.value = err.message
    return
  }
  if (data.session) {
    router.replace('/dashboard')
  } else {
    // Give Supabase a moment to exchange the code then retry
    setTimeout(async () => {
      const { data: d2 } = await supabase.auth.getSession()
      if (d2.session) {
        router.replace('/dashboard')
      } else {
        error.value = 'Sign-in failed — please try again.'
        setTimeout(() => router.replace('/login'), 2000)
      }
    }, 1000)
  }
})
</script>
