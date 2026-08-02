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

  it('repeats weekly on the days picked, starting from the date', async () => {
    apiCallMock.mockImplementation(async () => ({ id: 'r1' }))
    const w = mountIt()
    await w.get('[data-testid="schedule-open"]').trigger('click')
    await w.get('[data-testid="mode-repeat"]').trigger('click')
    await w.get('[data-testid="schedule-date"]').setValue('2026-08-03')
    await w.get('[data-testid="weekday-1"]').trigger('click') // Monday
    await w.get('[data-testid="weekday-4"]').trigger('click') // Thursday
    await w.get('[data-testid="schedule-save"]').trigger('click')
    await flushPromises()

    const post = apiCallMock.mock.calls.at(-1)!
    expect(String(post[0])).toBe('/workouts/recurrence')
    expect(JSON.parse((post[1] as { body: string }).body)).toEqual({
      template_id: 't1',
      byweekday: [1, 4],
      starts_on: '2026-08-03',
    })
    expect(w.emitted('scheduled')).toHaveLength(1)
  })

  it('will not save a repeat with no days picked', async () => {
    // It would be a pattern that silently never fires.
    const w = mountIt()
    await w.get('[data-testid="schedule-open"]').trigger('click')
    await w.get('[data-testid="mode-repeat"]').trigger('click')
    await w.get('[data-testid="schedule-date"]').setValue('2026-08-03')
    expect(w.get('[data-testid="schedule-save"]').attributes('disabled')).toBeDefined()
  })

  it('a day can be unpicked again', async () => {
    const w = mountIt()
    await w.get('[data-testid="schedule-open"]').trigger('click')
    await w.get('[data-testid="mode-repeat"]').trigger('click')
    await w.get('[data-testid="weekday-1"]').trigger('click')
    expect(w.get('[data-testid="weekday-1"]').attributes('aria-pressed')).toBe('true')
    await w.get('[data-testid="weekday-1"]').trigger('click')
    expect(w.get('[data-testid="weekday-1"]').attributes('aria-pressed')).toBe('false')
  })

  it('stays a one-off unless repeating is chosen', async () => {
    apiCallMock.mockImplementation(async () => ({ id: 'sch1' }))
    const w = mountIt()
    await w.get('[data-testid="schedule-open"]').trigger('click')
    expect(w.find('[data-testid="weekday-chips"]').exists()).toBe(false)
    await w.get('[data-testid="schedule-date"]').setValue('2026-08-03')
    await w.get('[data-testid="schedule-save"]').trigger('click')
    await flushPromises()
    expect(String(apiCallMock.mock.calls.at(-1)![0])).toBe('/workouts/schedule')
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
