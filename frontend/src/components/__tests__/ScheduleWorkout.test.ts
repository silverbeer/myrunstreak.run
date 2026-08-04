import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const apiCallMock = vi.fn()
vi.mock('@/config/api', () => ({ apiCall: (...a: unknown[]) => apiCallMock(...a) }))

import ScheduleWorkout from '../ScheduleWorkout.vue'

const isoDaysFromNow = (n: number): string => {
  const d = new Date()
  d.setDate(d.getDate() + n)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const todayISO = (): string => isoDaysFromNow(0)

// Dates must be derived, never written down. The component refuses to schedule
// into the past, so a hardcoded date silently stops being savable the morning it
// expires — and the failure surfaces in the WRONG test, because of the shared
// mock below. That is exactly how this suite broke in CI (a UTC runner had
// already rolled over to the next day while the author's machine had not).
const SOON = isoDaysFromNow(3)

const mountIt = () =>
  mount(ScheduleWorkout, { props: { templateId: 't1', athleteId: 'ath1' } })

// No shared mock reset: clearing a vi.fn between tests drops Vitest's handle on
// a promise it recorded, and the rejection below is then reported as unhandled
// even though the component catches it. Each test sets its own implementation.
//
// The cost is that `mock.calls` accumulates across tests, so a test asserting on
// the last call must first prove its OWN call happened — otherwise it reads the
// previous test's and reports a confusing mismatch instead of "nothing posted".
const lastCallAfter = (before: number): unknown[] => {
  expect(apiCallMock.mock.calls.length).toBeGreaterThan(before)
  return apiCallMock.mock.calls.at(-1)!
}
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
    await w.get('[data-testid="schedule-date"]').setValue(SOON)
    await w.get('[data-testid="schedule-save"]').trigger('click')
    await flushPromises()

    expect(apiCallMock).toHaveBeenCalledWith('/workouts/schedule', {
      method: 'POST',
      body: JSON.stringify({ template_id: 't1', scheduled_for: SOON }),
      headers: { 'X-Act-As-Athlete': 'ath1' },
    })
    expect(w.emitted('scheduled')).toHaveLength(1)
    expect(w.find('[data-testid="schedule-form"]').exists()).toBe(false)
  })

  it('repeats weekly on the days picked, starting from the date', async () => {
    apiCallMock.mockImplementation(async () => ({ id: 'r1' }))
    const w = mountIt()
    const before = apiCallMock.mock.calls.length
    await w.get('[data-testid="schedule-open"]').trigger('click')
    await w.get('[data-testid="mode-repeat"]').trigger('click')
    await w.get('[data-testid="schedule-date"]').setValue(SOON)
    await w.get('[data-testid="weekday-1"]').trigger('click') // Monday
    await w.get('[data-testid="weekday-4"]').trigger('click') // Thursday
    await w.get('[data-testid="schedule-save"]').trigger('click')
    await flushPromises()

    const post = lastCallAfter(before)
    expect(String(post[0])).toBe('/workouts/recurrence')
    expect(JSON.parse((post[1] as { body: string }).body)).toEqual({
      template_id: 't1',
      byweekday: [1, 4],
      starts_on: SOON,
    })
    expect(w.emitted('scheduled')).toHaveLength(1)
  })

  it('will not save a repeat with no days picked', async () => {
    // It would be a pattern that silently never fires.
    const w = mountIt()
    await w.get('[data-testid="schedule-open"]').trigger('click')
    await w.get('[data-testid="mode-repeat"]').trigger('click')
    await w.get('[data-testid="schedule-date"]').setValue(SOON)
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
    const before = apiCallMock.mock.calls.length
    await w.get('[data-testid="schedule-open"]').trigger('click')
    expect(w.find('[data-testid="weekday-chips"]').exists()).toBe(false)
    await w.get('[data-testid="schedule-date"]').setValue(SOON)
    await w.get('[data-testid="schedule-save"]').trigger('click')
    await flushPromises()
    expect(String(lastCallAfter(before)[0])).toBe('/workouts/schedule')
  })

  it('explains a day that already has this plan on it', async () => {
    // The unique index is the guard; a raw constraint string is not an answer.
    apiCallMock.mockImplementation(async () => {
      throw new Error('duplicate key value violates unique constraint')
    })
    const w = mountIt()
    await w.get('[data-testid="schedule-open"]').trigger('click')
    await w.get('[data-testid="schedule-date"]').setValue(SOON)
    await w.get('[data-testid="schedule-save"]').trigger('click')
    await flushPromises()

    expect(w.get('[data-testid="schedule-error"]').text()).toContain('already on the calendar')
    // The form stays open with the day still in it — nothing to retype.
    expect(w.find('[data-testid="schedule-form"]').exists()).toBe(true)
    expect(w.emitted('scheduled')).toBeUndefined()
  })
})
