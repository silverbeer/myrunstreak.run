import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import RouteMap from '../RouteMap.vue'
import type { RunTrack } from '@/types/runs'

// jsdom has no matchMedia; force prefers-reduced-motion so the draw-on
// animation resolves to "show everything" synchronously.
beforeEach(() => {
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener() {}, removeEventListener() {} }))
})

const track: RunTrack = {
  activity_id: 'act-1',
  has_track: true,
  lat: [42.0, 42.001, 42.002, 42.003],
  lon: [-71.0, -71.001, -71.002, -71.001],
  elevation_m: [10, 12, 14, 11],
  heart_rate: [140, 150, 160, 150],
  pace_min_per_km: [6.0, 6.0, 5.0, 7.0],
  dist_km: [0, 0.1, 0.2, 0.3],
  city: 'Worcester County',
  state: 'Massachusetts',
  date: '2026-07-21T08:32:00',
  distance_km: 6.88,
  duration_seconds: 2498,
  avg_pace_min_per_km: 6.05,
  weather_type: 'cloudy',
  temperature_celsius: 20.3,
}

describe('RouteMap', () => {
  it('renders one segment per pair of points', () => {
    const w = mount(RouteMap, { props: { track, unit: 'mi' } })
    // 4 points -> 3 connecting segments.
    expect(w.findAll('line').length).toBe(3)
  })

  it('offers a mode toggle for each metric with variation', () => {
    const w = mount(RouteMap, { props: { track, unit: 'mi' } })
    const labels = w.findAll('button').map((b) => b.text())
    expect(labels).toContain('Pace')
    expect(labels).toContain('Elevation')
    expect(labels).toContain('Heart rate')
  })

  it('hides a metric mode when its series is flat', () => {
    const flat = { ...track, heart_rate: [150, 150, 150, 150] }
    const w = mount(RouteMap, { props: { track: flat, unit: 'mi' } })
    const labels = w.findAll('button').map((b) => b.text())
    expect(labels).not.toContain('Heart rate')
  })

  it('shows the place name', () => {
    const w = mount(RouteMap, { props: { track, unit: 'mi' } })
    expect(w.text()).toContain('Worcester County, Massachusetts')
  })

  it('switches the coloured segments when the mode changes', async () => {
    const w = mount(RouteMap, { props: { track, unit: 'mi' } })
    const paceColors = w.findAll('line').map((l) => l.attributes('stroke'))
    const elevBtn = w.findAll('button').find((b) => b.text() === 'Elevation')!
    await elevBtn.trigger('click')
    const elevColors = w.findAll('line').map((l) => l.attributes('stroke'))
    expect(elevColors).not.toEqual(paceColors)
  })
})
