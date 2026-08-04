import { describe, expect, it } from 'vitest'
import { displayDecimals, displayUnit, toDisplay, toStored } from '@/utils/metrics'

describe('displayUnit', () => {
  it('converts stored units to what the user reads', () => {
    expect(displayUnit('km')).toBe('mi')
    expect(displayUnit('kg')).toBe('lb')
  })

  it('reads a workout count as workouts, not "session" (SB-509)', () => {
    expect(displayUnit('session')).toBe('workouts')
  })

  it('passes through units that need no translation', () => {
    expect(displayUnit('reps')).toBe('reps')
  })
})

describe('toDisplay / toStored', () => {
  it('round-trips distance and weight', () => {
    expect(toStored('km', toDisplay('km', 10))).toBeCloseTo(10, 6)
    expect(toStored('kg', toDisplay('kg', 80))).toBeCloseTo(80, 6)
  })

  it('leaves counted units alone — a workout is a workout in any locale', () => {
    expect(toDisplay('session', 12)).toBe(12)
    expect(toStored('session', 12)).toBe(12)
    expect(toDisplay('reps', 50)).toBe(50)
  })
})

describe('displayDecimals', () => {
  it('shows counts whole and measurements to one place', () => {
    expect(displayDecimals('session')).toBe(0)
    expect(displayDecimals('reps')).toBe(0)
    expect(displayDecimals('km')).toBe(1)
  })
})
