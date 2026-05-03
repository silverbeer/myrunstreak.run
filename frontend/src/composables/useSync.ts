import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { SyncResponse } from '@/types/runs'

const LAST_SYNC_KEY = 'mrs.lastSyncAt'

const syncing = ref(false)
const error = ref<string | null>(null)
const lastSyncedAt = ref<string | null>(loadLastSync())

function loadLastSync(): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(LAST_SYNC_KEY)
}

function persistLastSync(iso: string): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(LAST_SYNC_KEY, iso)
  }
}

export function useSync() {
  const sync = async (): Promise<SyncResponse | null> => {
    syncing.value = true
    error.value = null
    try {
      const res = await apiCall<SyncResponse>('/sync-user', { method: 'POST' })
      const now = new Date().toISOString()
      lastSyncedAt.value = now
      persistLastSync(now)
      return res
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Sync failed'
      return null
    } finally {
      syncing.value = false
    }
  }

  return { sync, syncing, error, lastSyncedAt }
}
