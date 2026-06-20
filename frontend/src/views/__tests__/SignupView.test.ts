import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SignupView from '../SignupView.vue'
import { useAuthStore } from '@/stores/auth'

const buildRouter = () =>
  createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>home</div>' } },
      { path: '/login', component: { template: '<div>login</div>' } },
      { path: '/signup', component: SignupView },
      { path: '/dashboard', component: { template: '<div>dash</div>' } },
    ],
  })

const mountAt = async (query: string) => {
  const router = buildRouter()
  await router.push(`/signup${query}`)
  await router.isReady()
  const w = mount(SignupView, { global: { plugins: [createPinia(), router] } })
  await flushPromises()
  return { w, router }
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('SignupView', () => {
  it('shows invite-only notice when no token in the link', async () => {
    const { w } = await mountAt('')
    expect(w.text()).toContain('invite-only')
    expect(w.find('input[type="password"]').exists()).toBe(false)
  })

  it('renders the redeem form when an invite token is present', async () => {
    const { w } = await mountAt('?invite=tok-abcdef')
    expect(w.findAll('input[type="password"]').length).toBe(2)
  })

  it('redeems and routes to dashboard on success', async () => {
    const { w, router } = await mountAt('?invite=tok-abcdef')
    const auth = useAuthStore()
    const spy = vi.spyOn(auth, 'redeemInvite').mockResolvedValue({ success: true })
    const push = vi.spyOn(router, 'push')

    const pwds = w.findAll('input[type="password"]')
    await pwds[0].setValue('secret1')
    await pwds[1].setValue('secret1')
    await w.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(spy).toHaveBeenCalledWith('tok-abcdef', 'secret1')
    expect(push).toHaveBeenCalledWith('/dashboard')
  })

  it('does not redeem when passwords mismatch', async () => {
    const { w } = await mountAt('?invite=tok-abcdef')
    const auth = useAuthStore()
    const spy = vi.spyOn(auth, 'redeemInvite').mockResolvedValue({ success: true })

    const pwds = w.findAll('input[type="password"]')
    await pwds[0].setValue('secret1')
    await pwds[1].setValue('secret2')
    await w.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(spy).not.toHaveBeenCalled()
    expect(w.text()).toContain("Passwords don't match")
  })
})
