import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RouteFrequency from '../RouteFrequency.vue'
import type { RunRoute } from '@/types/runs'

const shaped: RunRoute = {
  run_count: 189,
  rank: 1,
  total_routes: 27,
  best_pace_min_per_km: 5.04,
  variant_run_count: 41,
  variant_best_pace_min_per_km: 5.1,
}

const mountIt = (route: RunRoute | null | undefined) =>
  mount(RouteFrequency, { props: { route, unit: 'mi' } })

describe('RouteFrequency', () => {
  it('shows the family count, rank and variant split', () => {
    const text = mountIt(shaped).text()
    expect(text).toContain('189')
    expect(text).toContain('#1 of 27 routes')
    expect(text).toContain('41')
    expect(text).toContain('8:07 /mi') // 5.04 min/km
    expect(text).toContain("you've run this exact version 41 times")
  })

  it('renders nothing when the run has no route (treadmill / no GPS)', () => {
    expect(mountIt(null).find('[data-testid="route-frequency"]').exists()).toBe(false)
    expect(mountIt(undefined).find('[data-testid="route-frequency"]').exists()).toBe(false)
  })

  it('renders nothing for a route run only once', () => {
    const once: RunRoute = { ...shaped, run_count: 1, variant_run_count: 1 }
    expect(mountIt(once).find('[data-testid="route-frequency"]').exists()).toBe(false)
  })

  it('renders nothing without shape data, where run_count is not a route count', () => {
    // Coarse start-cell grouping: no variant_run_count. 1009 "runs of this
    // route" would really be every run of this distance from this area.
    const coarse = { run_count: 1009, rank: 1, total_routes: 207, best_pace_min_per_km: 5.04 }
    expect(mountIt(coarse).find('[data-testid="route-frequency"]').exists()).toBe(false)
  })

  it('drops the variant note when every run used the same version', () => {
    const single: RunRoute = { ...shaped, run_count: 12, variant_run_count: 12 }
    const text = mountIt(single).text()
    expect(text).toContain('12')
    expect(text).not.toContain('exact version')
  })
})
