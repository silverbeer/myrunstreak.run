import { describe, it, expect, vi, beforeEach } from 'vitest'

const getUserMock = vi.fn()
const updateUserMock = vi.fn().mockResolvedValue({ data: {}, error: null })

vi.mock('@/config/supabase', () => ({
  supabase: {
    auth: {
      getUser: getUserMock,
      updateUser: updateUserMock,
    },
  },
}))

describe('useUserPreferences', () => {
  beforeEach(() => {
    window.localStorage.clear()
    getUserMock.mockReset()
    updateUserMock.mockClear()
    vi.resetModules()
  })

  it('defaults to mi when nothing is stored', async () => {
    getUserMock.mockResolvedValue({ data: { user: { user_metadata: {} } } })
    const { useUserPreferences } = await import('../useUserPreferences')
    const { unit } = useUserPreferences()
    expect(unit.value).toBe('mi')
  })

  it('reads unit from localStorage on initial load', async () => {
    window.localStorage.setItem('mrs.unit', 'km')
    getUserMock.mockResolvedValue({ data: { user: { user_metadata: {} } } })
    const { useUserPreferences } = await import('../useUserPreferences')
    const { unit } = useUserPreferences()
    expect(unit.value).toBe('km')
  })

  it('overrides local with Supabase user_metadata when present', async () => {
    window.localStorage.setItem('mrs.unit', 'mi')
    getUserMock.mockResolvedValue({
      data: { user: { user_metadata: { unit: 'km' } } },
    })
    const { useUserPreferences } = await import('../useUserPreferences')
    const { unit, loaded } = useUserPreferences()
    await vi.waitFor(() => expect(loaded.value).toBe(true))
    expect(unit.value).toBe('km')
    expect(window.localStorage.getItem('mrs.unit')).toBe('km')
  })

  it('persists changes to localStorage and Supabase via setUnit', async () => {
    getUserMock.mockResolvedValue({ data: { user: { user_metadata: {} } } })
    const { useUserPreferences } = await import('../useUserPreferences')
    const { unit, setUnit } = useUserPreferences()

    await setUnit('km')
    expect(unit.value).toBe('km')
    expect(window.localStorage.getItem('mrs.unit')).toBe('km')
    expect(updateUserMock).toHaveBeenCalledWith({ data: { unit: 'km' } })
  })
})
