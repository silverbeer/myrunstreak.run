import { describe, it, expect } from 'vitest'
import { WEEKDAY_CHIPS, describeRecurrence } from '@/composables/useWorkoutRecurrence'

describe('describeRecurrence (SB-535)', () => {
  it('reads a pattern back in weekday order', () => {
    // Stored order should not leak into what the athlete reads.
    expect(describeRecurrence([4, 1])).toBe('Every Mon, Thu')
    expect(describeRecurrence([1])).toBe('Every Mon')
  })

  it('says "Every day" rather than listing all seven', () => {
    expect(describeRecurrence([0, 1, 2, 3, 4, 5, 6])).toBe('Every day')
  })

  it('numbers Sunday first, matching Date.getDay()', () => {
    // The stored values come from the UI, so this convention has to hold on
    // both sides — Python converts once, in the expansion helper.
    expect(describeRecurrence([0])).toBe('Every Sun')
    expect(describeRecurrence([6])).toBe('Every Sat')
    expect(WEEKDAY_CHIPS.map((c) => c.value)).toEqual([0, 1, 2, 3, 4, 5, 6])
    expect(WEEKDAY_CHIPS[0].label).toBe('Su')
  })
})
