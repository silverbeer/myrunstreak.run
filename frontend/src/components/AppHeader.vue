<template>
  <header class="bg-white shadow-sm sticky top-0 z-50">
    <nav class="container-app py-4">
      <div class="flex items-center justify-between">
        <RouterLink to="/" class="flex items-center hover:opacity-80 transition">
          <BrandLogo :size="52" />
        </RouterLink>

        <div class="hidden md:flex items-center space-x-6">
          <RouterLink
            v-for="link in navLinks"
            :key="link.path"
            :to="link.path"
            class="text-gray-700 hover:text-brand-600 font-medium transition"
            active-class="text-brand-600"
          >
            {{ link.name }}
          </RouterLink>
          <SyncButton v-if="auth.isAuthenticated" mode="compact" />
          <button @click="handleSignOut" class="btn-secondary text-sm">
            Sign out
          </button>
        </div>

        <button
          @click="mobileMenuOpen = !mobileMenuOpen"
          class="md:hidden text-gray-700 hover:text-brand-600"
          :aria-label="mobileMenuOpen ? 'Close menu' : 'Open menu'"
          :aria-expanded="mobileMenuOpen"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              v-if="!mobileMenuOpen"
              stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M4 6h16M4 12h16M4 18h16"
            />
            <path
              v-else
              stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <div v-if="mobileMenuOpen" class="md:hidden mt-4 space-y-2">
        <RouterLink
          v-for="link in navLinks"
          :key="link.path"
          :to="link.path"
          class="block text-gray-700 hover:text-brand-600 font-medium py-2"
          active-class="text-brand-600"
          @click="mobileMenuOpen = false"
        >
          {{ link.name }}
        </RouterLink>
        <button @click="handleSignOut" class="block text-gray-700 hover:text-brand-600 font-medium py-2">
          Sign out
        </button>
      </div>
    </nav>
  </header>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useMyAthlete, useRoles } from '@/composables/useCoach'
import BrandLogo from '@/components/BrandLogo.vue'
import SyncButton from '@/components/SyncButton.vue'

const auth = useAuthStore()
const router = useRouter()
const mobileMenuOpen = ref(false)

const { isCoach, isAdmin, loadRoles } = useRoles()
const { myAthlete, loadMyAthlete } = useMyAthlete()

// Coach link → coaches/admins (SB-189 P4-1). My Profile → linked athletes (SB-219).
// Admin link → admins only (SB-223).
const navLinks = computed(() => [
  { name: 'Dashboard', path: '/dashboard' },
  { name: 'Runs', path: '/runs' },
  ...(isCoach.value ? [{ name: 'Coach', path: '/coach' }] : []),
  ...(isCoach.value ? [{ name: 'Catalog', path: '/exercises' }] : []),
  ...(isAdmin.value ? [{ name: 'Admin', path: '/admin' }] : []),
  ...(myAthlete.value ? [{ name: 'My Profile', path: '/profile' }] : []),
  { name: 'Settings', path: '/settings' },
])

// Refetch role/athlete gating whenever the logged-in user changes — not just
// on mount — so an SPA login (no full page reload) reveals the Coach / My
// Profile links immediately (force past the module-scoped cache).
watch(
  () => auth.user?.id,
  (id) => {
    if (id) {
      loadRoles(true)
      loadMyAthlete(true)
    }
  },
  { immediate: true },
)

const handleSignOut = async () => {
  mobileMenuOpen.value = false
  await auth.signOut()
  router.push('/login')
}
</script>
