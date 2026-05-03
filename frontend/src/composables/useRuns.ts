import { ref, computed } from 'vue'
import { apiCall } from '@/config/api'
import type { PaginatedRun, RunsResponse } from '@/types/runs'

export function useRuns(pageSize = 25) {
  const runs = ref<PaginatedRun[]>([])
  const total = ref(0)
  const offset = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const page = computed(() => Math.floor(offset.value / pageSize) + 1)
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
  const hasPrev = computed(() => offset.value > 0)
  const hasNext = computed(() => offset.value + pageSize < total.value)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      const res = await apiCall<RunsResponse>(
        `/runs?offset=${offset.value}&limit=${pageSize}`,
      )
      runs.value = res.runs
      total.value = res.total
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load runs'
    } finally {
      loading.value = false
    }
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
    page,
    totalPages,
    hasPrev,
    hasNext,
    load,
    next,
    prev,
  }
}
