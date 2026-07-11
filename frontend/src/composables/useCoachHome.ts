import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { CoachHome } from '@/types/coach'

/** The coach landing aggregate (SB-266) — one call, everything the page shows. */
export function useCoachHome() {
  const home = ref<CoachHome | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      home.value = await apiCall<CoachHome>('/coach/home')
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load coach home'
    } finally {
      loading.value = false
    }
  }

  return { home, loading, error, load }
}
