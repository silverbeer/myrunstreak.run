import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../supabase', () => ({
  supabase: { auth: { getSession: async () => ({ data: { session: null } }) } },
}))

import { apiCall } from '../api'

const respond = (status: number, body: unknown) => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: false,
      status,
      headers: { get: () => null },
      json: async () => body,
    })),
  )
}

const failure = async (): Promise<Error & { status?: number }> => {
  try {
    await apiCall('/whatever')
  } catch (e) {
    return e as Error & { status?: number }
  }
  throw new Error('expected apiCall to throw')
}

beforeEach(() => {
  vi.unstubAllGlobals()
})

describe('apiCall error messages (SB-523)', () => {
  it('reads FastAPI 422 validation arrays instead of falling back to the status', async () => {
    // The shape that produced a bare "HTTP 422" on the print sheet: `detail` is
    // an ARRAY, so `detail.message` was undefined and every branch missed.
    respond(422, {
      detail: [
        { loc: ['header', 'x-act-as-athlete'], msg: 'value is not a valid uuid' },
      ],
    })
    const err = await failure()
    expect(err.message).toContain('x-act-as-athlete')
    expect(err.message).toContain('not a valid uuid')
    expect(err.message).not.toBe('HTTP 422')
  })

  it('joins several validation failures', async () => {
    respond(422, {
      detail: [
        { loc: ['body', 'name'], msg: 'field required' },
        { loc: ['body', 'rounds'], msg: 'must be positive' },
      ],
    })
    const err = await failure()
    expect(err.message).toBe('name: field required; rounds: must be positive')
  })

  it('still handles a plain string detail', async () => {
    respond(404, { detail: 'Template not found' })
    expect((await failure()).message).toBe('Template not found')
  })

  it('still handles a structured object detail (SB-349 dup-athlete 409)', async () => {
    respond(409, { detail: { code: 'dup', message: 'Athlete already exists' } })
    expect((await failure()).message).toBe('Athlete already exists')
  })

  it('falls back to the status only when the body says nothing useful', async () => {
    respond(500, {})
    const err = await failure()
    expect(err.message).toBe('HTTP 500')
    expect(err.status).toBe(500)
  })

  it('attaches the status so callers can explain the failure', async () => {
    respond(403, { detail: 'nope' })
    expect((await failure()).status).toBe(403)
  })
})
