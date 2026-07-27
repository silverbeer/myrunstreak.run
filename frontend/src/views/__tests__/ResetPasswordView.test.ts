import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

// Mock the Supabase client the view + store use.
const getSessionMock = vi.fn()
const updateUserMock = vi.fn()
const signOutMock = vi.fn().mockResolvedValue({})
vi.mock('@/config/supabase', () => ({
  supabase: {
    auth: {
      getSession: (...a: unknown[]) => getSessionMock(...a),
      updateUser: (...a: unknown[]) => updateUserMock(...a),
      signOut: (...a: unknown[]) => signOutMock(...a),
      onAuthStateChange: vi.fn(),
    },
  },
}))

import ResetPasswordView from '../ResetPasswordView.vue'

const buildRouter = () =>
  createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>home</div>' } },
      { path: '/login', component: { template: '<div>login</div>' } },
      { path: '/auth/reset-password', component: ResetPasswordView },
    ],
  })

const mountWithHash = async (hash: string) => {
  Object.defineProperty(window, 'location', {
    value: { hash, origin: 'http://localhost:5174' },
    writable: true,
  })
  const router = buildRouter()
  await router.push(`/auth/reset-password${hash}`)
  await router.isReady()
  const w = mount(ResetPasswordView, { global: { plugins: [createPinia(), router] } })
  await flushPromises()
  return { w }
}

const withSession = () => getSessionMock.mockResolvedValue({ data: { session: { access_token: 't' } } })
const noSession = () => getSessionMock.mockResolvedValue({ data: { session: null } })

beforeEach(() => {
  setActivePinia(createPinia())
  getSessionMock.mockReset()
  updateUserMock.mockReset()
  signOutMock.mockClear()
})

describe('ResetPasswordView (recovery session, SB-171)', () => {
  it('shows expired state when the hash carries an error', async () => {
    noSession()
    const { w } = await mountWithHash('#error=access_denied&error_code=otp_expired')
    expect(w.text()).toContain('expired or was already used')
    expect(w.find('form').exists()).toBe(false)
  })

  it('shows invalid state when there is no recovery session', async () => {
    noSession()
    const { w } = await mountWithHash('')
    expect(w.text()).toContain('needs a valid password-reset link')
    expect(w.find('form').exists()).toBe(false)
  })

  it('renders the form when a recovery session exists', async () => {
    withSession()
    const { w } = await mountWithHash('#access_token=tok&type=recovery')
    expect(w.find('form').exists()).toBe(true)
    expect(w.find('#new-password').exists()).toBe(true)
  })

  it('blocks submit when passwords do not match', async () => {
    withSession()
    const { w } = await mountWithHash('#access_token=tok&type=recovery')
    await w.find('#new-password').setValue('hunter22hunter22')
    await w.find('#confirm-password').setValue('different11different')
    await w.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(w.text()).toContain('Passwords do not match')
    expect(updateUserMock).not.toHaveBeenCalled()
  })

  it('updates the password via the recovery session, then signs out', async () => {
    withSession()
    updateUserMock.mockResolvedValue({ error: null })
    const { w } = await mountWithHash('#access_token=tok&type=recovery')
    await w.find('#new-password').setValue('hunter22hunter22')
    await w.find('#confirm-password').setValue('hunter22hunter22')
    await w.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(updateUserMock).toHaveBeenCalledWith({ password: 'hunter22hunter22' })
    expect(signOutMock).toHaveBeenCalled()
    expect(w.text()).toContain('Password updated')
  })

  it('surfaces the error when the update fails', async () => {
    withSession()
    updateUserMock.mockResolvedValue({ error: { message: 'Token expired' } })
    const { w } = await mountWithHash('#access_token=tok&type=recovery')
    await w.find('#new-password').setValue('hunter22hunter22')
    await w.find('#confirm-password').setValue('hunter22hunter22')
    await w.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(w.text()).toContain('Token expired')
  })
})
