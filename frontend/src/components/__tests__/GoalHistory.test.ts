import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import GoalHistory from '../GoalHistory.vue'
import type { GoalHistoryItem } from '@/types/runs'

// Fixed "now" so the current-period ("Active") logic is deterministic:
// June 2026 is the current month.
const FIXED_NOW = new Date('2026-06-15T12:00:00Z')

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(FIXED_NOW)
})

afterEach(() => {
  vi.useRealTimers()
})

const item = (over: Partial<GoalHistoryItem>): GoalHistoryItem => ({
  goal_mi: 200,
  progress_mi: 200,
  percent: 100,
  text: null,
  fetched_at: null,
  year: 2026,
  month: 5,
  period: 'month',
  hit: true,
  ...over,
})

const sample: GoalHistoryItem[] = [
  item({ period: 'year', month: null, goal_mi: 1200, progress_mi: 690, percent: 57.5, hit: false }),
  item({ month: 6, goal_mi: 130, progress_mi: 60, percent: 46, hit: false }), // current → Active
  item({ month: 5, goal_mi: 125, progress_mi: 125.3, percent: 100.2, hit: true }), // Hit
  item({ month: 4, goal_mi: 121, progress_mi: 110, percent: 90.9, hit: false }), // Missed
]

describe('GoalHistory', () => {
  it('is collapsed initially and shows no rows', () => {
    const w = mount(GoalHistory, { props: { items: sample, loading: false } })
    expect(w.text()).toContain('Goal history')
    expect(w.text()).not.toContain('May')
  })

  it('emits expand on first open (parent lazy-loads)', async () => {
    const w = mount(GoalHistory, { props: { items: [], loading: false } })
    await w.find('button').trigger('click')
    expect(w.emitted('expand')).toHaveLength(1)
  })

  it('groups by year and renders month rows when open', async () => {
    const w = mount(GoalHistory, { props: { items: sample, loading: false } })
    await w.find('button').trigger('click')
    const text = w.text()
    expect(text).toContain('2026')
    expect(text).toContain('Apr')
    expect(text).toContain('May')
    expect(text).toContain('Jun')
  })

  it('badges hit / missed / active correctly', async () => {
    const w = mount(GoalHistory, { props: { items: sample, loading: false } })
    await w.find('button').trigger('click')
    const text = w.text()
    expect(text).toContain('Hit') // May
    expect(text).toContain('Missed') // April (past, not reached)
    expect(text).toContain('Active') // June (current month, in progress)
  })

  it('shows loading state', async () => {
    const w = mount(GoalHistory, { props: { items: [], loading: true } })
    await w.find('button').trigger('click')
    expect(w.text()).toContain('Loading')
  })

  it('shows empty state when no goals and not loading', async () => {
    const w = mount(GoalHistory, { props: { items: [], loading: false } })
    await w.find('button').trigger('click')
    expect(w.text()).toContain('No past goals')
  })
})
