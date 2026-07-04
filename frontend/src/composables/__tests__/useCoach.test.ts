import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the API layer; each test drives responses by path via mockImplementation.
const apiCallMock = vi.fn()
vi.mock('@/config/api', () => ({
  apiCall: (...args: unknown[]) => apiCallMock(...args),
}))

// Fresh module per test so the module-scoped roles cache (shared by useRoles /
// AppHeader) doesn't leak between cases.
async function freshModule() {
  vi.resetModules()
  return import('../useCoach')
}

beforeEach(() => {
  apiCallMock.mockReset()
})

describe('useRoles / isCoach gating', () => {
  it('is false before roles load', async () => {
    const { useRoles } = await freshModule()
    const { isCoach } = useRoles()
    expect(isCoach.value).toBe(false)
  })

  it('is true when the coach role is present', async () => {
    apiCallMock.mockResolvedValue({ roles: ['coach'], is_admin: false })
    const { useRoles } = await freshModule()
    const { isCoach, loadRoles } = useRoles()
    await loadRoles()
    expect(isCoach.value).toBe(true)
  })

  it('is true for an admin even without the coach role', async () => {
    apiCallMock.mockResolvedValue({ roles: [], is_admin: true })
    const { useRoles } = await freshModule()
    const { isCoach, loadRoles } = useRoles()
    await loadRoles()
    expect(isCoach.value).toBe(true)
  })

  it('is false for a plain user', async () => {
    apiCallMock.mockResolvedValue({ roles: [], is_admin: false })
    const { useRoles } = await freshModule()
    const { isCoach, loadRoles } = useRoles()
    await loadRoles()
    expect(isCoach.value).toBe(false)
  })

  it('caches roles — second load does not refetch unless forced', async () => {
    apiCallMock.mockResolvedValue({ roles: ['coach'], is_admin: false })
    const { useRoles } = await freshModule()
    const { loadRoles } = useRoles()
    await loadRoles()
    await loadRoles()
    expect(apiCallMock).toHaveBeenCalledTimes(1)
    await loadRoles(true)
    expect(apiCallMock).toHaveBeenCalledTimes(2)
  })

  it('degrades to no-role on a failed roles fetch', async () => {
    apiCallMock.mockRejectedValue(new Error('boom'))
    const { useRoles } = await freshModule()
    const { isCoach, loadRoles } = useRoles()
    await loadRoles()
    expect(isCoach.value).toBe(false)
  })

  it('isAdmin tracks is_admin only (not coach role)', async () => {
    apiCallMock.mockResolvedValue({ roles: ['coach'], is_admin: false })
    const { useRoles } = await freshModule()
    const { isAdmin, loadRoles } = useRoles()
    expect(isAdmin.value).toBe(false)
    await loadRoles()
    expect(isAdmin.value).toBe(false) // coach but not admin
  })

  it('isAdmin is true for an admin', async () => {
    apiCallMock.mockResolvedValue({ roles: [], is_admin: true })
    const { useRoles } = await freshModule()
    const { isAdmin, loadRoles } = useRoles()
    await loadRoles()
    expect(isAdmin.value).toBe(true)
  })
})

describe('coach invites (admin)', () => {
  it('inviteCoach POSTs email + grant_role=coach and returns the invite', async () => {
    const invite = { id: 'i1', token: 'tok123', email: 'c@x.com', grant_role: 'coach' }
    apiCallMock.mockResolvedValue(invite)
    const { inviteCoach } = await freshModule()
    const result = await inviteCoach('c@x.com')
    expect(result).toEqual(invite)
    const [path, opts] = apiCallMock.mock.calls[0]
    expect(path).toBe('/invites')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ email: 'c@x.com', grant_role: 'coach' })
  })

  it('listInvites GETs /invites', async () => {
    apiCallMock.mockResolvedValue([{ id: 'i1', token: 't', email: 'c@x.com' }])
    const { listInvites } = await freshModule()
    const result = await listInvites()
    expect(apiCallMock).toHaveBeenCalledWith('/invites')
    expect(result).toHaveLength(1)
  })
})

describe('useCoach roster', () => {
  it('loads athletes into state', async () => {
    apiCallMock.mockResolvedValue([
      { id: 'a1', display_name: 'Kid', birth_year: 2011, linked_user_id: null, created_by: 'c1', notes: null, created_at: 'x' },
    ])
    const { useCoach } = await freshModule()
    const { athletes, loadAthletes } = useCoach()
    await loadAthletes()
    expect(apiCallMock).toHaveBeenCalledWith('/athletes')
    expect(athletes.value).toHaveLength(1)
    expect(athletes.value[0].display_name).toBe('Kid')
  })

  it('createAthlete POSTs, appends to the roster, and returns the created row', async () => {
    const created = { id: 'a2', display_name: 'New', birth_year: null, linked_user_id: null, created_by: 'c1', notes: null, created_at: 'x' }
    apiCallMock.mockResolvedValue(created)
    const { useCoach } = await freshModule()
    const { athletes, createAthlete } = useCoach()
    const result = await createAthlete({ display_name: 'New' })
    expect(result).toEqual(created)
    expect(athletes.value).toContainEqual(created)
    const [path, opts] = apiCallMock.mock.calls[0]
    expect(path).toBe('/athletes')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ display_name: 'New' })
  })

  it('createAthlete surfaces an error and returns null on failure', async () => {
    apiCallMock.mockRejectedValue(new Error('nope'))
    const { useCoach } = await freshModule()
    const { athletes, error, createAthlete } = useCoach()
    const result = await createAthlete({ display_name: 'X' })
    expect(result).toBeNull()
    expect(error.value).toBe('nope')
    expect(athletes.value).toHaveLength(0)
  })
})

describe('useAthleteDetail act-as', () => {
  it('loads the athlete and their sessions with the X-Act-As-Athlete header', async () => {
    const athlete = { id: 'a1', display_name: 'Kid', birth_year: 2011, linked_user_id: null, created_by: 'c1', notes: null, created_at: 'x' }
    apiCallMock.mockImplementation((path: string) => {
      if (path === '/athletes/a1') return Promise.resolve(athlete)
      if (path.startsWith('/workouts/sessions')) return Promise.resolve([{ id: 's1', athlete_id: 'a1', session_date: '2026-07-01', type: 'circuit', total_minutes: 30, how_felt: 'good', notes: null, sets: [] }])
      return Promise.reject(new Error('unexpected ' + path))
    })
    const { useAthleteDetail } = await freshModule()
    const { athlete: a, sessions, load } = useAthleteDetail('a1')
    await load()

    expect(a.value?.display_name).toBe('Kid')
    expect(sessions.value).toHaveLength(1)

    const sessionsCall = apiCallMock.mock.calls.find((c) => String(c[0]).startsWith('/workouts/sessions'))
    expect(sessionsCall).toBeTruthy()
    expect(sessionsCall![1].headers).toEqual({ 'X-Act-As-Athlete': 'a1' })
  })

  it('captures an error when the athlete load fails', async () => {
    apiCallMock.mockRejectedValue(new Error('403'))
    const { useAthleteDetail } = await freshModule()
    const { error, load } = useAthleteDetail('a1')
    await load()
    expect(error.value).toBe('403')
  })
})
