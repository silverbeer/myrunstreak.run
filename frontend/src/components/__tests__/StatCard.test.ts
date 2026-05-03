import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatCard from '../StatCard.vue'

describe('StatCard', () => {
  it('renders label and value', () => {
    const w = mount(StatCard, { props: { label: 'Total Runs', value: 234 } })
    expect(w.text()).toContain('Total Runs')
    expect(w.text()).toContain('234')
  })

  it('renders sublabel when provided', () => {
    const w = mount(StatCard, {
      props: { label: 'Distance', value: '12.5 mi', sublabel: 'this week' },
    })
    expect(w.text()).toContain('this week')
  })

  it('omits sublabel when absent', () => {
    const w = mount(StatCard, { props: { label: 'X', value: 1 } })
    const subs = w.findAll('p').filter((p) => p.classes().includes('text-gray-500'))
    expect(subs.length).toBe(0)
  })

  it('applies custom valueClass', () => {
    const w = mount(StatCard, {
      props: { label: 'X', value: 1, valueClass: 'text-brand-600' },
    })
    const valueEl = w.findAll('p').find((p) => p.text() === '1')
    expect(valueEl?.classes()).toContain('text-brand-600')
  })
})
