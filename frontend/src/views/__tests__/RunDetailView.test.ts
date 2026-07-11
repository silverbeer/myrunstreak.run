import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const apiCallMock = vi.fn()
vi.mock('@/config/api', () => ({
  apiCall: (...args: unknown[]) => apiCallMock(...args),
}))
vi.mock('@/composables/useUserPreferences', async () => {
  const { ref } = await import('vue')
  return { useUserPreferences: () => ({ unit: ref('mi') }) }
})
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { activityId: 'act-123' } }),
  RouterLink: { template: '<a><slot /></a>' },
}))
vi.mock('vue3-apexcharts', () => ({
  default: { name: 'ApexChart', template: '<div class="apex-stub" />' },
}))

import RunDetailView from '../RunDetailView.vue'

const detail = {
  activity_id: 'act-123',
  date: '2026-07-10T06:45:00',
  distance_km: 5.31,
  duration_seconds: 3141,
  avg_pace_min_per_km: 9.86,
  weather: { temperature_celsius: 27.8, weather_type: 'hot', humidity_percent: 82, wind_speed_kph: 9 },
  vitals: { heart_rate_avg: 151, heart_rate_min: 128, heart_rate_max: 167, cadence_avg: 169 },
  how_felt: null,
  notes: null,
  splits: [
    { split_number: 1, split_unit: 'mi', cumulative_distance_km: 1.609, cumulative_seconds: 612, pace_min_per_km: 9.51, heart_rate: 142, elevation_gain_m: 12, elevation_loss_m: 4 },
    { split_number: 2, split_unit: 'mi', cumulative_distance_km: 3.219, cumulative_seconds: 1254, pace_min_per_km: 9.98, heart_rate: 150, elevation_gain_m: 29, elevation_loss_m: 15 },
  ],
}

beforeEach(() => {
  apiCallMock.mockReset()
})

describe('RunDetailView (SB-263)', () => {
  it('renders hero, weather badge and the hot+humid callout', async () => {
    apiCallMock.mockResolvedValue(detail)
    const w = mount(RunDetailView)
    await flushPromises()

    expect(apiCallMock).toHaveBeenCalledWith('/runs/act-123')
    expect(w.text()).toContain('hot')
    expect(w.text()).toContain('82% humidity')
    expect(w.text()).toContain('82°F') // default unit mi -> Fahrenheit
    expect(w.text()).toContain('Hot + humid') // heat-stress callout (27.8C / 82%)
    expect(w.text()).toContain('Mile splits')
    expect(w.text()).toContain('Elevation')
    expect(w.text()).toContain('167 bpm')
  })

  it('no heat callout on a cool run', async () => {
    apiCallMock.mockResolvedValue({
      ...detail,
      weather: { ...detail.weather, temperature_celsius: 10, humidity_percent: 40, weather_type: 'clear' },
    })
    const w = mount(RunDetailView)
    await flushPromises()
    expect(w.text()).not.toContain('Hot + humid')
  })

  it('hides splits + elevation cards when a run has no splits', async () => {
    apiCallMock.mockResolvedValue({ ...detail, splits: [] })
    const w = mount(RunDetailView)
    await flushPromises()
    expect(w.text()).not.toContain('splits')
    expect(w.text()).not.toContain('Elevation')
  })
})
