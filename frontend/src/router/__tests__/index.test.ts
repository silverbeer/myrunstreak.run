import { describe, it, expect, vi, beforeEach } from 'vitest'

// Auth store: always authenticated with a session so the guard skips init.
const authState = {
  session: {},
  loading: false,
  isAuthenticated: true,
  initialize: vi.fn(),
}
vi.mock('@/stores/auth', () => ({ useAuthStore: () => authState }))

// Roles drive the requiresCoach guard. Tests set rolesRef.value per case.
const rolesRef: { value: { roles: string[]; is_admin: boolean } | null } = { value: null }
const loadRolesMock = vi.fn(async () => {})
vi.mock('@/composables/useCoach', () => ({
  useRoles: () => ({ roles: rolesRef, loadRoles: loadRolesMock }),
}))

// resolveLanding is where a redirected non-coach is sent.
const resolveLandingMock = vi.fn(async () => '/dashboard')
vi.mock('@/composables/useLanding', () => ({
  resolveLanding: () => resolveLandingMock(),
}))

import router from '../index'

beforeEach(async () => {
  loadRolesMock.mockClear()
  resolveLandingMock.mockClear()
  rolesRef.value = null
  await router.replace('/dashboard')
  await router.isReady()
})

describe('router requiresCoach guard (SB-331)', () => {
  it('redirects a non-coach away from /coach', async () => {
    rolesRef.value = { roles: [], is_admin: false }
    await router.push('/coach')
    expect(resolveLandingMock).toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('redirects a non-coach away from a coach sub-route', async () => {
    rolesRef.value = { roles: [], is_admin: false }
    await router.push('/coach/a1')
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('lets a coach reach /coach', async () => {
    rolesRef.value = { roles: ['coach'], is_admin: false }
    await router.push('/coach')
    expect(resolveLandingMock).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/coach')
  })

  it('lets an admin reach /coach', async () => {
    rolesRef.value = { roles: [], is_admin: true }
    await router.push('/coach')
    expect(router.currentRoute.value.path).toBe('/coach')
  })
})
