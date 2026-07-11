import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the API layer; tests drive responses by path via mockImplementation.
const apiCallMock = vi.fn()
vi.mock('@/config/api', () => ({
  apiCall: (...args: unknown[]) => apiCallMock(...args),
}))

// Fresh module per test — both the landing cache and useCoach's roles cache
// are module-scoped.
async function freshModule() {
  vi.resetModules()
  return import('../useLanding')
}

function mockApi(roles: { roles: string[]; is_admin: boolean }, totalRuns: number) {
  apiCallMock.mockImplementation((path: string) => {
    if (path === '/me/roles') return Promise.resolve(roles)
    if (path === '/stats/overall') return Promise.resolve({ total_runs: totalRuns })
    return Promise.reject(new Error(`unexpected call: ${path}`))
  })
}

beforeEach(() => {
  apiCallMock.mockReset()
})

describe('resolveLanding (SB-265)', () => {
  it('coach with no runs lands on Coach', async () => {
    mockApi({ roles: ['coach'], is_admin: false }, 0)
    const { resolveLanding } = await freshModule()
    expect(await resolveLanding()).toBe('/coach')
  })

  it('coach who also runs keeps the dashboard', async () => {
    mockApi({ roles: ['coach'], is_admin: false }, 42)
    const { resolveLanding } = await freshModule()
    expect(await resolveLanding()).toBe('/dashboard')
  })

  it('plain runner lands on the dashboard without a stats call', async () => {
    apiCallMock.mockImplementation((path: string) => {
      if (path === '/me/roles') return Promise.resolve({ roles: [], is_admin: false })
      return Promise.reject(new Error(`unexpected call: ${path}`))
    })
    const { resolveLanding } = await freshModule()
    expect(await resolveLanding()).toBe('/dashboard')
    expect(apiCallMock).not.toHaveBeenCalledWith('/stats/overall')
  })

  it('admin with runs keeps the dashboard', async () => {
    mockApi({ roles: [], is_admin: true }, 500)
    const { resolveLanding } = await freshModule()
    expect(await resolveLanding()).toBe('/dashboard')
  })

  it('falls back to the dashboard when stats fail', async () => {
    apiCallMock.mockImplementation((path: string) => {
      if (path === '/me/roles') return Promise.resolve({ roles: ['coach'], is_admin: false })
      return Promise.reject(new Error('boom'))
    })
    const { resolveLanding } = await freshModule()
    expect(await resolveLanding()).toBe('/dashboard')
  })

  it('caches the decision until reset', async () => {
    mockApi({ roles: ['coach'], is_admin: false }, 0)
    const { resolveLanding, resetLanding } = await freshModule()
    expect(await resolveLanding()).toBe('/coach')
    apiCallMock.mockClear()
    expect(await resolveLanding()).toBe('/coach')
    expect(apiCallMock).not.toHaveBeenCalled()

    // After reset it re-resolves — same coach, now with runs -> dashboard.
    resetLanding()
    mockApi({ roles: ['coach'], is_admin: false }, 42)
    expect(await resolveLanding()).toBe('/dashboard')
  })
})
