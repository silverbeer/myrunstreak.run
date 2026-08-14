import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('@/config/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'test-token' } } }),
    },
  },
}))

const fetchMock = vi.fn()

const IMPORTED = {
  status: 'imported',
  activity_id: 'gpx-abc123',
  run_id: '3f0d0f6e-0000-0000-0000-000000000000',
  distance_km: 8.05,
  duration_seconds: 2700,
  start_date_time_local: '2026-08-10T07:15:00-04:00',
  has_track: true,
}

const okJson = (body: unknown) => ({
  ok: true,
  status: 200,
  headers: new Headers(),
  json: async () => body,
})

const file = (name: string, size = 1024): File => {
  const f = new File(['x'], name)
  Object.defineProperty(f, 'size', { value: size })
  return f
}

describe('useImport', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockReset()
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uploads the file as multipart and returns the result', async () => {
    fetchMock.mockResolvedValueOnce(okJson(IMPORTED))
    const { useImport } = await import('../useImport')
    const { importFile, result, error } = useImport()

    const out = await importFile(file('run.gpx'))

    expect(out).toEqual(IMPORTED)
    expect(result.value).toEqual(IMPORTED)
    expect(error.value).toBeNull()

    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toContain('/import/activity')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    // The browser must set Content-Type itself so the multipart boundary is
    // included; sending our own would break parsing server-side.
    expect(init.headers['Content-Type']).toBeUndefined()
    expect(init.headers['Authorization']).toBe('Bearer test-token')
  })

  it('sends the browser timezone so the run lands on the right date', async () => {
    fetchMock.mockResolvedValueOnce(okJson(IMPORTED))
    const { useImport } = await import('../useImport')

    await useImport().importFile(file('run.gpx'))

    const body = fetchMock.mock.calls[0][1].body as FormData
    expect(body.get('timezone')).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone)
    expect((body.get('file') as File).name).toBe('run.gpx')
  })

  it('surfaces a duplicate as a result, not an error', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ ...IMPORTED, status: 'duplicate' }))
    const { useImport } = await import('../useImport')
    const { importFile, error } = useImport()

    const out = await importFile(file('run.gpx'))

    expect(out?.status).toBe('duplicate')
    expect(error.value).toBeNull()
  })

  it('rejects an unsupported extension without uploading', async () => {
    const { useImport } = await import('../useImport')
    const { importFile, error } = useImport()

    const out = await importFile(file('photo.png'))

    expect(out).toBeNull()
    expect(error.value).toContain(".png can't be imported")
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('rejects an oversized file without uploading', async () => {
    const { useImport } = await import('../useImport')
    const { importFile, error } = useImport()

    const out = await importFile(file('huge.gpx', 11 * 1024 * 1024))

    expect(out).toBeNull()
    expect(error.value).toContain('the limit is 10 MB')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('rejects an empty file without uploading', async () => {
    const { useImport } = await import('../useImport')
    const { importFile, error } = useImport()

    expect(await importFile(file('empty.gpx', 0))).toBeNull()
    expect(error.value).toBe('That file is empty.')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("keeps the server's reason when a parse fails", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 422,
      headers: new Headers(),
      json: async () => ({ detail: 'Trackpoints carry no timestamps, so the run has no duration.' }),
    })
    const { useImport } = await import('../useImport')
    const { importFile, error, result } = useImport()

    expect(await importFile(file('bad.gpx'))).toBeNull()
    expect(error.value).toBe('Trackpoints carry no timestamps, so the run has no duration.')
    expect(result.value).toBeNull()
  })

  it('validates against the server allowlist once formats load', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ extensions: ['.gpx'], max_bytes: 1024, default_timezone: 'UTC' })
    )
    const { useImport } = await import('../useImport')
    const { loadFormats, validate } = useImport()

    await loadFormats()

    expect(validate(file('run.gpx', 100))).toBeNull()
    expect(validate(file('run.tcx', 100))).toContain("can't be imported")
    expect(validate(file('run.gpx', 2048))).toContain('the limit is')
  })

  it('falls back to built-in formats when the formats call fails', async () => {
    fetchMock.mockRejectedValueOnce(new Error('offline'))
    const { useImport } = await import('../useImport')
    const { loadFormats, formats, validate } = useImport()

    await loadFormats()

    expect(formats.value.extensions).toContain('.tcx')
    expect(validate(file('run.tcx', 100))).toBeNull()
  })

  it('clears the previous outcome on reset', async () => {
    fetchMock.mockResolvedValueOnce(okJson(IMPORTED))
    const { useImport } = await import('../useImport')
    const { importFile, reset, result } = useImport()

    await importFile(file('run.gpx'))
    expect(result.value).not.toBeNull()

    reset()
    expect(result.value).toBeNull()
  })
})
