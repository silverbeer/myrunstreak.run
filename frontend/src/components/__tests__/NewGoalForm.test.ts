import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const apiCall = vi.fn()
vi.mock('@/config/api', () => ({
  apiCall: (...args: unknown[]) => apiCall(...args),
}))

import NewGoalForm from '../NewGoalForm.vue'
import type { MetricType } from '@/types/metrics'

const types: MetricType[] = [
  { key: 'running_distance', display_name: 'Running distance', unit: 'km', aggregation: 'sum', higher_is_better: true },
  { key: 'pushups', display_name: 'Push-ups', unit: 'reps', aggregation: 'sum', higher_is_better: true },
]

beforeEach(() => apiCall.mockReset())

function lastBody(): Record<string, unknown> {
  const [, opts] = apiCall.mock.calls[apiCall.mock.calls.length - 1]
  return JSON.parse((opts as RequestInit).body as string)
}

describe('NewGoalForm', () => {
  it('does not render when show is false', () => {
    const w = mount(NewGoalForm, { props: { show: false, types } })
    expect(w.find('form').exists()).toBe(false)
  })

  it('converts a volume target from display units (mi) to stored (km)', async () => {
    apiCall.mockResolvedValueOnce({ id: 'g1' })
    const w = mount(NewGoalForm, { props: { show: true, types } })

    const selects = w.findAll('select')
    await selects[0].setValue('running_distance') // metric
    await selects[1].setValue('volume') // kind
    await selects[2].setValue('month') // period
    await w.find('input[type="number"]').setValue(100) // 100 mi

    await w.find('form').trigger('submit')
    await flushPromises()

    expect(apiCall).toHaveBeenCalledWith('/metrics/goals', expect.objectContaining({ method: 'POST' }))
    const body = lastBody()
    expect(body.metric_key).toBe('running_distance')
    expect(body.kind).toBe('volume')
    expect(body.comparator).toBe('gte')
    expect(body.target as number).toBeCloseTo(160.93, 1) // 100 mi → km
    expect(w.emitted('created')).toBeTruthy()
  })

  it('sends a plain count (no conversion) for a frequency goal with rest_budget', async () => {
    apiCall.mockResolvedValueOnce({ id: 'g2' })
    const w = mount(NewGoalForm, { props: { show: true, types } })

    const selects = w.findAll('select')
    await selects[0].setValue('pushups')
    await selects[1].setValue('frequency')
    await selects[2].setValue('week')
    await w.find('input[type="number"]').setValue(5)

    await w.find('form').trigger('submit')
    await flushPromises()

    const body = lastBody()
    expect(body.metric_key).toBe('pushups')
    expect(body.kind).toBe('frequency')
    expect(body.target).toBe(5)
    expect(body.rest_budget).toBe(0)
  })

  it('requires period bounds for a custom period before submitting', async () => {
    const w = mount(NewGoalForm, { props: { show: true, types } })
    const selects = w.findAll('select')
    await selects[1].setValue('volume')
    await selects[2].setValue('custom')
    await w.find('input[type="number"]').setValue(50)

    await w.find('form').trigger('submit')
    await flushPromises()

    // No dates → invalid → no API call.
    expect(apiCall).not.toHaveBeenCalled()
  })
})
