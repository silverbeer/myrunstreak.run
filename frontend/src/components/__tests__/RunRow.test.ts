import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RunRow from '../RunRow.vue'

const baseProps = {
  date: '2026-05-01T08:00:00',
  distanceKm: 10,
  durationSeconds: 3000,
  paceMinPerKm: 5.0,
}

describe('RunRow', () => {
  it('formats distance in km when unit=km', () => {
    const w = mount(RunRow, { props: { ...baseProps, unit: 'km' } })
    expect(w.text()).toContain('10.00 km')
  })

  it('converts distance to miles when unit=mi', () => {
    // 10 km = 6.21 mi
    const w = mount(RunRow, { props: { ...baseProps, unit: 'mi' } })
    expect(w.text()).toContain('6.21 mi')
  })

  it('renders the formatted date', () => {
    const w = mount(RunRow, { props: { ...baseProps, unit: 'km' } })
    // 2026-05-01 is a Friday
    expect(w.text()).toContain('Fri May 1')
  })

  it('renders duration as mm:ss', () => {
    const w = mount(RunRow, { props: { ...baseProps, unit: 'km' } })
    // 3000 seconds = 50:00
    expect(w.text()).toContain('50:00')
  })

  it('falls back to durationMinutes when seconds not provided', () => {
    const w = mount(RunRow, {
      props: {
        date: baseProps.date,
        distanceKm: baseProps.distanceKm,
        paceMinPerKm: baseProps.paceMinPerKm,
        durationMinutes: 50,
        unit: 'km',
      },
    })
    expect(w.text()).toContain('50:00')
  })

  it('shows weather text when provided', () => {
    const w = mount(RunRow, {
      props: { ...baseProps, unit: 'km', weather: 'Sunny' },
    })
    expect(w.text()).toContain('Sunny')
  })
})
