import { ref, computed } from 'vue'
import { apiCall } from '@/config/api'
import type { PaginatedRun, RunFilters, RunsResponse } from '@/types/runs'

export function useRuns(pageSize = 25) {
  const runs = ref<PaginatedRun[]>([])
  const total = ref(0)
  const offset = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const filters = ref<RunFilters>({})

  const page = computed(() => Math.floor(offset.value / pageSize) + 1)
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
  const hasPrev = computed(() => offset.value > 0)
  const hasNext = computed(() => offset.value + pageSize < total.value)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams({
        offset: String(offset.value),
        limit: String(pageSize),
      })
      for (const [k, v] of Object.entries(filters.value)) {
        if (v !== undefined && v !== null) params.set(k, String(v))
      }
      const res = await apiCall<RunsResponse>(`/runs?${params.toString()}`)
      runs.value = res.runs
      total.value = res.total
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load runs'
    } finally {
      loading.value = false
    }
  }

  /** Replace the active filters and reload from page 1 (SB-268). */
  const setFilters = async (next: RunFilters): Promise<void> => {
    filters.value = next
    offset.value = 0
    await load()
  }

  const next = async (): Promise<void> => {
    if (!hasNext.value) return
    offset.value += pageSize
    await load()
  }

  const prev = async (): Promise<void> => {
    if (!hasPrev.value) return
    offset.value = Math.max(0, offset.value - pageSize)
    await load()
  }

  return {
    runs,
    total,
    offset,
    loading,
    error,
    filters,
    page,
    totalPages,
    hasPrev,
    hasNext,
    load,
    setFilters,
    next,
    prev,
  }
}
