import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ResetPasswordView from '../ResetPasswordView.vue'
import { useAuthStore } from '@/stores/auth'

const buildRouter = () =>
  createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>home</div>' } },
      { path: '/login', component: { template: '<div>login</div>' } },
      {
        path: '/auth/reset-password',
        component: ResetPasswordView,
      },
    ],
  })

const mountWithHash = async (hash: string) => {
  // jsdom respects window.location.hash if we set it before mount
  Object.defineProperty(window, 'location', {
    value: { hash, origin: 'http://localhost:5174' },
    writable: true,
  })
  const router = buildRouter()
  await router.push(`/auth/reset-password${hash}`)
  await router.isReady()

  const w = mount(ResetPasswordView, {
    global: { plugins: [createPinia(), router] },
  })
  await flushPromises()
  return { w, router }
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('ResetPasswordView', () => {
  it('shows missing-token state when URL hash has no access_token', async () => {
    const { w } = await mountWithHash('')
    expect(w.text()).toContain('missing a recovery token')
    expect(w.find('form').exists()).toBe(false)
  })

  it('renders the new-password form when access_token is present', async () => {
    const { w } = await mountWithHash('#access_token=tok&type=recovery')
    expect(w.find('form').exists()).toBe(true)
    expect(w.find('#new-password').exists()).toBe(true)
    expect(w.find('#confirm-password').exists()).toBe(true)
  })

  it('blocks submit when passwords do not match', async () => {
    const { w } = await mountWithHash('#access_token=tok&type=recovery')

    await w.find('#new-password').setValue('hunter22hunter22')
    await w.find('#confirm-password').setValue('different11different')
    await w.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(w.text()).toContain('Passwords do not match')
  })

  it('calls applyPasswordReset with the token + new password on submit', async () => {
    const { w } = await mountWithHash('#access_token=recovery-tok&type=recovery')

    const auth = useAuthStore()
    const spy = vi
      .spyOn(auth, 'applyPasswordReset')
      .mockResolvedValue({ success: true })

    await w.find('#new-password').setValue('hunter22hunter22')
    await w.find('#confirm-password').setValue('hunter22hunter22')
    await w.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(spy).toHaveBeenCalledWith('recovery-tok', 'hunter22hunter22')
    expect(w.text()).toContain('Password updated')
  })

  it('shows the auth-store error when the apply call fails', async () => {
    const { w } = await mountWithHash('#access_token=recovery-tok')

    const auth = useAuthStore()
    vi.spyOn(auth, 'applyPasswordReset').mockImplementation(async () => {
      auth.error = 'Token expired'
      return { success: false, error: 'Token expired' }
    })

    await w.find('#new-password').setValue('hunter22hunter22')
    await w.find('#confirm-password').setValue('hunter22hunter22')
    await w.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(w.text()).toContain('Token expired')
  })
})
