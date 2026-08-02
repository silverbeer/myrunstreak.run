import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const apiCallMock = vi.fn()
vi.mock('@/config/api', () => ({ apiCall: (...a: unknown[]) => apiCallMock(...a) }))

import ScheduleWorkout from '../ScheduleWorkout.vue'

const todayISO = (): string => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const mountIt = () =>
  mount(ScheduleWorkout, { props: { templateId: 't1', athleteId: 'ath1' } })

// No shared mock reset: clearing a vi.fn between tests drops Vitest's handle on
// a promise it recorded, and the rejection below is then reported as unhandled
// even though the component catches it. Each test sets its own implementation.
describe('ScheduleWorkout (SB-534)', () => {
  it('will not schedule into the past', async () => {
    const w = mountIt()
    await w.get('[data-testid="schedule-open"]').trigger('click')
    expect(w.get('[data-testid="schedule-date"]').attributes('min')).toBe(todayISO())
  })

  it('cannot be saved until a day is picked', async () => {
    const w = mountIt()
    await w.get('[data-testid="schedule-open"]').trigger('click')
    expect(w.get('[data-testid="schedule-save"]').attributes('disabled')).toBeDefined()
  })

  it('posts the occasion and closes', async () => {
    apiCallMock.mockResolvedValue({ id: 'sch1' })
    const w = mountIt()
    await w.get('[data-testid="schedule-open"]').trigger('click')
    await w.get('[data-testid="schedule-date"]').setValue('2026-08-06')
    await w.get('[data-testid="schedule-save"]').trigger('click')
    await flushPromises()

    expect(apiCallMock).toHaveBeenCalledWith('/workouts/schedule', {
      method: 'POST',
      body: JSON.stringify({ template_id: 't1', scheduled_for: '2026-08-06' }),
      headers: { 'X-Act-As-Athlete': 'ath1' },
    })
    expect(w.emitted('scheduled')).toHaveLength(1)
    expect(w.find('[data-testid="schedule-form"]').exists()).toBe(false)
  })

  it('explains a day that already has this plan on it', async () => {
    // The unique index is the guard; a raw constraint string is not an answer.
    apiCallMock.mockImplementation(async () => {
      throw new Error('duplicate key value violates unique constraint')
    })
    const w = mountIt()
    await w.get('[data-testid="schedule-open"]').trigger('click')
    await w.get('[data-testid="schedule-date"]').setValue('2026-08-06')
    await w.get('[data-testid="schedule-save"]').trigger('click')
    await flushPromises()

    expect(w.get('[data-testid="schedule-error"]').text()).toContain('already on the calendar')
    // The form stays open with the day still in it — nothing to retype.
    expect(w.find('[data-testid="schedule-form"]').exists()).toBe(true)
    expect(w.emitted('scheduled')).toBeUndefined()
  })
})
