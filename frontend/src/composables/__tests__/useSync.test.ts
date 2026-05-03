import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('@/config/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'test-token' } } }),
    },
  },
}))

const fetchMock = vi.fn()

describe('useSync', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockReset()
    window.localStorage.clear()
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('starts not syncing with no error', async () => {
    const { useSync } = await import('../useSync')
    const { syncing, error } = useSync()
    expect(syncing.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('flips syncing during request and stores lastSyncedAt on success', async () => {
    const responseBody = { message: 'ok', runs_synced: 3, since: '2026-05-01', until: '2026-05-03' }
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: async () => responseBody,
    })

    const { useSync } = await import('../useSync')
    const { sync, syncing, lastSyncedAt } = useSync()

    expect(lastSyncedAt.value).toBeNull()
    const result = await sync()

    expect(result).toEqual(responseBody)
    expect(syncing.value).toBe(false)
    expect(lastSyncedAt.value).not.toBeNull()
    expect(window.localStorage.getItem('mrs.lastSyncAt')).toBe(lastSyncedAt.value)
  })

  it('captures error on failure and leaves lastSyncedAt unchanged', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      headers: new Headers(),
      json: async () => ({ message: 'boom' }),
    })

    const { useSync } = await import('../useSync')
    const { sync, error, lastSyncedAt } = useSync()

    const result = await sync()

    expect(result).toBeNull()
    expect(error.value).toBe('boom')
    expect(lastSyncedAt.value).toBeNull()
  })
})
