import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import GoalsCard from '../GoalsCard.vue'
import type { GoalProgress } from '@/types/runs'

// Anchor the suite to a fixed date so pace math is deterministic.
// 2026 is non-leap; mid-May → ~36% of year, ~30% of month.
const FIXED_NOW = new Date('2026-05-09T12:00:00Z')

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(FIXED_NOW)
})

afterEach(() => {
  vi.useRealTimers()
})

const yearlyOnPace: GoalProgress = {
  goal_mi: 1200,
  progress_mi: 432,
  percent: 36,
  text: '1200 mi this year',
  fetched_at: '2026-05-09T12:00:00Z',
}

const monthlyBehind: GoalProgress = {
  goal_mi: 125,
  progress_mi: 13.5,
  percent: 10.8,
  text: 'In May I will run 125 miles',
  fetched_at: '2026-05-09T12:00:00Z',
}

const monthlyComplete: GoalProgress = {
  goal_mi: 100,
  progress_mi: 110,
  percent: 110,
  text: null,
  fetched_at: null,
}

describe('GoalsCard', () => {
  it('shows empty-state when both goals are null', () => {
    const w = mount(GoalsCard, { props: { yearly: null, monthly: null } })
    expect(w.text()).toContain('No goals set on SmashRun')
  })

  it('renders only yearly when monthly is null', () => {
    const w = mount(GoalsCard, { props: { yearly: yearlyOnPace, monthly: null } })
    expect(w.text()).toContain('1200')
    expect(w.text()).not.toContain('125')
  })

  it('renders only monthly when yearly is null', () => {
    const w = mount(GoalsCard, { props: { yearly: null, monthly: monthlyBehind } })
    expect(w.text()).toContain('125')
    expect(w.text()).not.toContain('1200')
  })

  it('renders progress in mi for both periods', () => {
    const w = mount(GoalsCard, { props: { yearly: yearlyOnPace, monthly: monthlyBehind } })
    expect(w.text()).toContain('432.0 / 1200 mi')
    expect(w.text()).toContain('13.5 / 125 mi')
  })

  it('shows goal text when present and omits the italic when null', () => {
    const w = mount(GoalsCard, { props: { yearly: yearlyOnPace, monthly: monthlyComplete } })
    expect(w.text()).toContain('1200 mi this year')
    // monthlyComplete has text: null → no italic paragraph for it
    const italicParas = w.findAll('p.italic')
    expect(italicParas.length).toBe(1)
  })

  it('flags a completed goal with celebration text', () => {
    const w = mount(GoalsCard, { props: { yearly: null, monthly: monthlyComplete } })
    expect(w.text()).toContain('Goal achieved!')
  })

  it('flags a behind-pace goal with the appropriate footer text', () => {
    // May 9 → expected ~9/31 ≈ 29%; actual 10.8% → behind by ~18% × 125 mi ≈ 22.6 mi behind
    const w = mount(GoalsCard, { props: { yearly: null, monthly: monthlyBehind } })
    expect(w.text()).toMatch(/behind pace/)
    expect(w.text()).not.toMatch(/ahead of pace/)
  })

  it('shows a catch-up line with days left and mi/day when behind', () => {
    // May 9, 31-day month → 22 days left; (125 - 13.5) / 22 ≈ 5.07 mi/day.
    const w = mount(GoalsCard, { props: { yearly: null, monthly: monthlyBehind } })
    expect(w.text()).toContain('22 days left')
    expect(w.text()).toContain('5.1 mi/day to finish')
  })

  it('omits the catch-up line when on/ahead of pace', () => {
    // yearlyOnPace is exactly on pace → no catch-up coaching.
    const w = mount(GoalsCard, { props: { yearly: yearlyOnPace, monthly: null } })
    expect(w.text()).not.toContain('to finish')
  })

  it('omits the catch-up line when the goal is already complete', () => {
    const w = mount(GoalsCard, { props: { yearly: null, monthly: monthlyComplete } })
    expect(w.text()).not.toContain('to finish')
  })

  it('uses the current month name in the monthly header', () => {
    // FIXED_NOW is 2026-05-09 → "May"
    const w = mount(GoalsCard, { props: { yearly: null, monthly: monthlyBehind } })
    expect(w.text()).toContain('May')
  })

  it('uses the current year in the yearly header', () => {
    const w = mount(GoalsCard, { props: { yearly: yearlyOnPace, monthly: null } })
    expect(w.text()).toContain('2026')
  })
})
