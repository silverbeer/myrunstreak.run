import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('@/config/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'test-token' } } }),
    },
  },
}))

const fetchMock = vi.fn()

describe('useDeleteRun', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockReset()
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('DELETEs the run and reports success', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 204,
      headers: new Headers({ 'content-length': '0' }),
      json: async () => null,
    })
    const { useDeleteRun } = await import('../useDeleteRun')
    const { remove, error } = useDeleteRun()

    expect(await remove('gpx-abc123')).toBe(true)
    expect(error.value).toBeNull()

    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toContain('/runs/gpx-abc123')
    expect(init.method).toBe('DELETE')
  })

  it('encodes the activity id', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 204,
      headers: new Headers({ 'content-length': '0' }),
      json: async () => null,
    })
    const { useDeleteRun } = await import('../useDeleteRun')

    await useDeleteRun().remove('tcx-2026-08-10T12:00:00Z')

    expect(fetchMock.mock.calls[0][0]).toContain('tcx-2026-08-10T12%3A00%3A00Z')
  })

  it("keeps the server's reason when a synced run is refused", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 409,
      headers: new Headers(),
      json: async () => ({
        detail:
          'Only imported runs can be deleted here. A synced run comes back on the next sync — remove it in SmashRun instead.',
      }),
    })
    const { useDeleteRun } = await import('../useDeleteRun')
    const { remove, error } = useDeleteRun()

    expect(await remove('act-42')).toBe(false)
    expect(error.value).toContain('comes back on the next sync')
  })

  it('reports a run that is gone', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      headers: new Headers(),
      json: async () => ({ detail: 'Run not found' }),
    })
    const { useDeleteRun } = await import('../useDeleteRun')
    const { remove, error } = useDeleteRun()

    expect(await remove('gpx-gone')).toBe(false)
    expect(error.value).toBe('Run not found')
  })
})
