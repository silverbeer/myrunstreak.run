import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  formatDistance,
  formatDistanceWithUnit,
  formatPace,
  formatDuration,
  formatDate,
  formatRelativeTime,
  distanceLabel,
} from '../format'

describe('distanceLabel', () => {
  it('returns mi for miles', () => {
    expect(distanceLabel('mi')).toBe('mi')
  })
  it('returns km for kilometers', () => {
    expect(distanceLabel('km')).toBe('km')
  })
})

describe('formatDistance', () => {
  it('returns km value as-is when unit is km', () => {
    expect(formatDistance(5.0, 'km')).toBe('5.00')
  })
  it('converts km to miles when unit is mi', () => {
    // 10 km = 6.21 mi (1.609344 km/mi)
    expect(formatDistance(10, 'mi')).toBe('6.21')
  })
  it('respects custom decimals', () => {
    expect(formatDistance(5.0, 'km', 0)).toBe('5')
    expect(formatDistance(5.0, 'km', 1)).toBe('5.0')
  })
  it('handles zero', () => {
    expect(formatDistance(0, 'km')).toBe('0.00')
    expect(formatDistance(0, 'mi')).toBe('0.00')
  })
})

describe('formatDistanceWithUnit', () => {
  it('formats km with unit suffix', () => {
    expect(formatDistanceWithUnit(5.0, 'km')).toBe('5.00 km')
  })
  it('formats miles with unit suffix', () => {
    expect(formatDistanceWithUnit(10, 'mi')).toBe('6.21 mi')
  })
})

describe('formatPace', () => {
  it('formats km pace correctly', () => {
    // 5.18 min/km = 5:11 /km
    expect(formatPace(5.18, 'km')).toBe('5:11 /km')
  })
  it('converts km pace to mi pace', () => {
    // 5.0 min/km × 1.609344 = 8.047 min/mi = 8:03 /mi
    expect(formatPace(5.0, 'mi')).toBe('8:03 /mi')
  })
  it('rounds seconds correctly', () => {
    // 4.5 min/km = 4:30 /km
    expect(formatPace(4.5, 'km')).toBe('4:30 /km')
  })
  it('pads single-digit seconds', () => {
    // 5.05 min/km = 5:03 /km
    expect(formatPace(5.05, 'km')).toBe('5:03 /km')
  })
  it('returns dash for null', () => {
    expect(formatPace(null, 'km')).toBe('–')
    expect(formatPace(undefined, 'mi')).toBe('–')
  })
  it('returns dash for zero or negative', () => {
    expect(formatPace(0, 'km')).toBe('–')
    expect(formatPace(-1, 'km')).toBe('–')
  })
})

describe('formatDuration', () => {
  it('formats minutes:seconds', () => {
    expect(formatDuration(125)).toBe('2:05')
  })
  it('formats hours:minutes:seconds when over an hour', () => {
    expect(formatDuration(3725)).toBe('1:02:05')
  })
  it('handles zero', () => {
    expect(formatDuration(0)).toBe('0:00')
  })
  it('rounds fractional seconds', () => {
    expect(formatDuration(60.7)).toBe('1:01')
  })
})

describe('formatDate', () => {
  it('formats ISO date as Weekday Mon Day', () => {
    // 2026-05-03 is a Sunday
    expect(formatDate('2026-05-03T10:00:00')).toBe('Sun May 3')
  })
  it('handles different months', () => {
    expect(formatDate('2026-01-15T10:00:00')).toBe('Thu Jan 15')
    expect(formatDate('2026-12-25T10:00:00')).toBe('Fri Dec 25')
  })
  it('returns input on invalid date', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date')
  })
})

describe('formatRelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-03T12:00:00Z'))
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns "Never" for null', () => {
    expect(formatRelativeTime(null)).toBe('Never')
    expect(formatRelativeTime(undefined)).toBe('Never')
  })
  it('returns "Just now" for less than a minute ago', () => {
    expect(formatRelativeTime('2026-05-03T11:59:30Z')).toBe('Just now')
  })
  it('returns minutes for under an hour', () => {
    expect(formatRelativeTime('2026-05-03T11:30:00Z')).toBe('30m ago')
  })
  it('returns hours for under a day', () => {
    expect(formatRelativeTime('2026-05-03T10:00:00Z')).toBe('2h ago')
  })
  it('returns days for under a week', () => {
    expect(formatRelativeTime('2026-05-01T12:00:00Z')).toBe('2d ago')
  })
  it('falls back to absolute date past a week', () => {
    expect(formatRelativeTime('2026-04-20T12:00:00Z')).toMatch(/\w{3} Apr 20/)
  })
})
