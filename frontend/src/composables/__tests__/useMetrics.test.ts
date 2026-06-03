import { describe, it, expect, vi, beforeEach } from 'vitest'

const apiCall = vi.fn()
vi.mock('@/config/api', () => ({
  apiCall: (...args: unknown[]) => apiCall(...args),
}))

import { useMetrics } from '@/composables/useMetrics'

beforeEach(() => {
  apiCall.mockReset()
})

describe('useMetrics', () => {
  it('loadGoals fetches /metrics/goals and stores the result', async () => {
    apiCall.mockResolvedValueOnce([{ goal: { id: 'g1' }, progress: 5 }])
    const { goals, loadGoals } = useMetrics()
    await loadGoals()
    expect(apiCall).toHaveBeenCalledWith('/metrics/goals')
    expect(goals.value).toHaveLength(1)
  })

  it('loadTypes fetches /metrics/types', async () => {
    apiCall.mockResolvedValueOnce([{ key: 'pushups' }])
    const { types, loadTypes } = useMetrics()
    await loadTypes()
    expect(apiCall).toHaveBeenCalledWith('/metrics/types')
    expect(types.value).toHaveLength(1)
  })

  it('logEntry POSTs the metric_key and value', async () => {
    apiCall.mockResolvedValueOnce({ id: 'e1' })
    const { logEntry } = useMetrics()
    await logEntry('pushups', 25)
    expect(apiCall).toHaveBeenCalledWith('/metrics/entries', {
      method: 'POST',
      body: JSON.stringify({ metric_key: 'pushups', value: 25 }),
    })
  })

  it('loadGoals surfaces an error message on failure', async () => {
    apiCall.mockRejectedValueOnce(new Error('boom'))
    const { error, loadGoals } = useMetrics()
    await loadGoals()
    expect(error.value).toBe('boom')
  })
})
