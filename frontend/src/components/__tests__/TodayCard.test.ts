import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TodayCard from '../TodayCard.vue'
import type { GoalProgress, MetricGoal, MetricType } from '@/types/metrics'

const types: MetricType[] = [
  { key: 'pushups', display_name: 'Push-ups', unit: 'reps', aggregation: 'sum', higher_is_better: true },
  { key: 'body_weight', display_name: 'Body weight', unit: 'kg', aggregation: 'latest', higher_is_better: false },
]

function makeGoal(over: Partial<MetricGoal>): MetricGoal {
  return {
    id: 'g1',
    user_id: 'u1',
    metric_key: 'pushups',
    kind: 'volume',
    period: 'month',
    period_start: null,
    period_end: null,
    target: 100,
    comparator: 'gte',
    rest_budget: 0,
    status: 'active',
    ...over,
  }
}

function progress(over: Partial<GoalProgress> & { goal: MetricGoal }): GoalProgress {
  return {
    window_start: '2026-06-01',
    window_end: '2026-06-30',
    progress: 0,
    target: over.goal.target,
    percent: null,
    met: false,
    projected: null,
    on_pace: null,
    per_day_needed: null,
    ...over,
  }
}

describe('TodayCard', () => {
  it('shows empty state with no goals', () => {
    const w = mount(TodayCard, { props: { goals: [], types } })
    expect(w.text()).toContain('No active goals')
  })

  it('renders a volume goal with display unit and pace', () => {
    const g = progress({
      goal: makeGoal({ metric_key: 'pushups', kind: 'volume', target: 100 }),
      progress: 30,
      percent: 30,
      on_pace: false,
      projected: 90,
      per_day_needed: 13.5,
    })
    const w = mount(TodayCard, { props: { goals: [g], types } })
    expect(w.text()).toContain('Push-ups')
    expect(w.text()).toContain('30 / 100 reps')
    expect(w.text()).toContain('30%')
    expect(w.text()).toContain('on pace for 90 reps')
  })

  it('renders a frequency goal as days', () => {
    const g = progress({
      goal: makeGoal({ metric_key: 'body_weight', kind: 'frequency', period: 'week', target: 3 }),
      progress: 2,
      percent: 66.6,
    })
    const w = mount(TodayCard, { props: { goals: [g], types } })
    expect(w.text()).toContain('Body weight')
    expect(w.text()).toContain('2 of 3 days')
  })

  it('flags a met goal as achieved', () => {
    const g = progress({
      goal: makeGoal({ target: 100 }),
      progress: 120,
      percent: 120,
      met: true,
    })
    const w = mount(TodayCard, { props: { goals: [g], types } })
    expect(w.text()).toContain('Achieved')
  })
})
