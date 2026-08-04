import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const apiCallMock = vi.fn()
vi.mock('@/config/api', () => ({
  apiCall: (...args: unknown[]) => apiCallMock(...args),
}))
// Mutable, because this view serves BOTH routes and only the coach one carries
// an athleteId. Hardcoding the coach params is what let SB-522 ship unnoticed.
const COACH_ROUTE = { athleteId: 'a1', templateId: 't1' }
const OWN_ROUTE = { templateId: 't1' }
let routeParams: Record<string, string> = { ...COACH_ROUTE }
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: routeParams }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

// The athlete route has to resolve its own athletes-table row (SB-524).
const myAthlete: { value: { id: string } | null } = { value: { id: 'my-athlete-row' } }
const loadMyAthlete = vi.fn(async () => {})
vi.mock('@/composables/useCoach', () => ({
  useMyAthlete: () => ({ myAthlete, loadMyAthlete }),
}))

import WorkoutPrintView from '../WorkoutPrintView.vue'

const template = {
  id: 't1',
  name: 'Track Thursday',
  type: 'intervals',
  rounds: 1,
  source: 'Matthew',
  notes: 'Goal for final rep: 400m broken into 100m sections',
  items: [
    { id: 'i1', exercise_key: 'easy_jog', section: 'warmup', position: 0, target_reps: null, target_duration_seconds: null, target_load_kg: null, target_distance_m: 804, rest_seconds: null, variant: null, notes: '1/2 mile warm up' },
    { id: 'i2', exercise_key: 'interval_run', section: 'main', position: 1, target_reps: 3, target_duration_seconds: null, target_load_kg: null, target_distance_m: 200, rest_seconds: 120, variant: null, notes: null },
    { id: 'i3', exercise_key: 'interval_run', section: 'main', position: 2, target_reps: 1, target_duration_seconds: null, target_load_kg: null, target_distance_m: 400, rest_seconds: null, variant: null, notes: null,
      segments: [
        { distance_m: 100, target_s_min: 20, target_s_max: 22, label: '0-100' },
        { distance_m: 100, target_s_min: 15, target_s_max: null, label: '100-200' },
      ] },
  ],
}

const exercises = [
  { key: 'easy_jog', display_name: 'Easy jog', measures: ['distance_m', 'duration_s'], cues: ['Conversational pace'], is_benchmark: false },
  { key: 'interval_run', display_name: 'Interval run', measures: ['distance_m', 'time_s'], cues: [], is_benchmark: true },
]

beforeEach(() => {
  routeParams = { ...COACH_ROUTE }
  myAthlete.value = { id: 'my-athlete-row' }
  loadMyAthlete.mockClear()
  apiCallMock.mockReset()
  apiCallMock.mockImplementation((path: string) => {
    if (path.startsWith('/workouts/templates/')) return Promise.resolve(template)
    if (path.startsWith('/athletes/')) return Promise.resolve({ id: 'a1', display_name: 'Gabe' })
    if (path === '/workouts/exercises') return Promise.resolve(exercises)
    return Promise.reject(new Error(`unexpected: ${path}`))
  })
})

describe('WorkoutPrintView (SB-231)', () => {
  it('renders the take-home sheet: title, meta blanks, sections', async () => {
    const w = mount(WorkoutPrintView)
    await flushPromises()
    expect(w.text()).toContain('Gabe — Track Thursday')
    expect(w.text()).toContain('Date:')
    expect(w.text()).toContain('Felt:')
    expect(w.text()).toContain('Warm-up')
    expect(w.text()).toContain('Workout')
    expect(w.text()).toContain('Great work!')
  })

  it('renders attempt rows for timed reps and segment goals for broken reps', async () => {
    const w = mount(WorkoutPrintView)
    await flushPromises()
    // 3x200 -> attempts 1..3 (interval_run measures time_s)
    expect(w.text()).toContain('Attempt')
    // broken 400 -> labeled segment rows with goals
    expect(w.text()).toContain('0-100')
    expect(w.text()).toContain('(20-22s)')
    expect(w.text()).toContain('100-200')
    expect(w.text()).toContain('(15s)')
  })

  it('acts as the athlete when fetching the template', async () => {
    mount(WorkoutPrintView)
    await flushPromises()
    expect(apiCallMock).toHaveBeenCalledWith(
      '/workouts/templates/t1',
      expect.objectContaining({ headers: { 'X-Act-As-Athlete': 'a1' } }),
    )
  })

  it('links back to the athlete when a coach is printing', async () => {
    const w = mount(WorkoutPrintView)
    await flushPromises()
    expect(w.get('a').attributes('href')).toBe('/coach/a1')
  })
})

describe('WorkoutPrintView on /my/workouts/print (SB-522)', () => {
  // Gabe printing his own workout got a bare HTTP 422: the view did
  // String(route.params.athleteId) on a route that has no athleteId, so the
  // literal string "undefined" went out as X-Act-As-Athlete and as
  // /athletes/undefined. The backend types that header as UUID and rejects the
  // request before any handler runs.

  it('scopes to the caller\'s own athlete row (SB-524)', async () => {
    // Not "no header": a coach-assigned template belongs to the ATHLETE row, so
    // an absent header queries `athlete_id IS NULL` and 404s. The scope id is
    // the athletes-table id, which is not the user id and is not in the URL.
    routeParams = { ...OWN_ROUTE }
    mount(WorkoutPrintView)
    await flushPromises()
    const call = apiCallMock.mock.calls.find((c) => c[0] === '/workouts/templates/t1')
    expect(call?.[1]?.headers).toEqual({ 'X-Act-As-Athlete': 'my-athlete-row' })
  })

  it('prints the caller’s own plan when they have no athlete row', async () => {
    // Used to refuse with "No athlete profile". A user who is nobody's athlete
    // still has plans of their own (SB-578) — the template is fetched with no
    // act-as header, which is what asks for their self-owned row.
    routeParams = { ...OWN_ROUTE }
    myAthlete.value = null
    mount(WorkoutPrintView)
    await flushPromises()

    const call = apiCallMock.mock.calls.find((c) => c[0] === '/workouts/templates/t1')
    expect(call).toBeDefined()
    expect(call?.[1]?.headers).toEqual({})
  })

  it('never sends the string "undefined" anywhere', async () => {
    routeParams = { ...OWN_ROUTE }
    mount(WorkoutPrintView)
    await flushPromises()
    const flat = JSON.stringify(apiCallMock.mock.calls)
    expect(flat).not.toContain('undefined')
  })

  it('skips the athlete lookup and titles the sheet with the workout alone', async () => {
    routeParams = { ...OWN_ROUTE }
    const w = mount(WorkoutPrintView)
    await flushPromises()
    expect(apiCallMock.mock.calls.some((c) => String(c[0]).startsWith('/athletes/'))).toBe(false)
    // Title is the workout alone — no dangling "— " where a name would go.
    expect(w.get('h1.sheet-title').text()).toBe('Track Thursday')
  })

  it('links back to /my/workouts, not a coach page', async () => {
    routeParams = { ...OWN_ROUTE }
    const w = mount(WorkoutPrintView)
    await flushPromises()
    expect(w.get('a').attributes('href')).toBe('/my/workouts')
  })
})

describe('WorkoutPrintView failure state (SB-523)', () => {
  // Gabe's whole experience of the bug was one line of red text reading
  // "HTTP 422". Whatever fails next, he should get a sentence and a way out.

  const fail = (message: string, status?: number) => {
    apiCallMock.mockReset()
    apiCallMock.mockImplementation(() => {
      const e = new Error(message) as Error & { status?: number }
      e.status = status
      return Promise.reject(e)
    })
  }

  it('explains the failure instead of printing a bare status', async () => {
    fail('HTTP 422', 422)
    const w = mount(WorkoutPrintView)
    await flushPromises()
    const panel = w.get('[data-testid="print-error"]')
    expect(panel.text()).toContain("Couldn't load this workout")
    expect(panel.text()).toContain('not something you did')
  })

  it('tailors the explanation to the status', async () => {
    fail('nope', 404)
    const w = mount(WorkoutPrintView)
    await flushPromises()
    expect(w.get('[data-testid="print-error"]').text()).toContain("doesn't exist any more")
  })

  it('keeps the raw message available for debugging', async () => {
    fail('HTTP 500', 500)
    const w = mount(WorkoutPrintView)
    await flushPromises()
    expect(w.get('[data-testid="print-error"]').text()).toContain('HTTP 500')
  })

  it('offers a retry that actually refetches', async () => {
    fail('HTTP 500', 500)
    const w = mount(WorkoutPrintView)
    await flushPromises()
    const before = apiCallMock.mock.calls.length

    // Recover, then retry: the sheet should render without a reload.
    apiCallMock.mockReset()
    apiCallMock.mockImplementation((path: string) => {
      if (path.startsWith('/workouts/templates/')) return Promise.resolve(template)
      if (path.startsWith('/athletes/')) return Promise.resolve({ id: 'a1', display_name: 'Gabe' })
      if (path === '/workouts/exercises') return Promise.resolve(exercises)
      return Promise.reject(new Error(`unexpected: ${path}`))
    })
    await w.get('[data-testid="print-retry"]').trigger('click')
    await flushPromises()

    expect(apiCallMock.mock.calls.length).toBeGreaterThan(0)
    expect(before).toBeGreaterThan(0)
    expect(w.find('[data-testid="print-error"]').exists()).toBe(false)
    expect(w.text()).toContain('Track Thursday')
  })

  it('offers a way out of the dead end', async () => {
    fail('HTTP 500', 500)
    const w = mount(WorkoutPrintView)
    await flushPromises()
    expect(w.get('[data-testid="print-error"]').text()).toContain('Back to workouts')
  })
})

describe('WorkoutPrintView rounds (SB-529)', () => {
  // `rounds` was only ever round-tripped as an integer — created, read back,
  // asserted equal. Nothing checked that a multi-round circuit is COMMUNICATED,
  // so if every consumer ignored the field the suite would still be green.
  // These fail if it stops being honoured.

  const withRounds = (rounds: number) => {
    apiCallMock.mockReset()
    apiCallMock.mockImplementation((path: string) => {
      if (path.startsWith('/workouts/templates/')) return Promise.resolve({ ...template, rounds })
      if (path.startsWith('/athletes/')) return Promise.resolve({ id: 'a1', display_name: 'Gabe' })
      if (path === '/workouts/exercises') return Promise.resolve(exercises)
      return Promise.reject(new Error(`unexpected: ${path}`))
    })
  }

  it('gives each round its own column to write in', async () => {
    // SB-528 turned rounds from a sentence into columns: three rounds is three
    // boxes per exercise, not the same exercise printed three times.
    withRounds(3)
    const w = mount(WorkoutPrintView)
    await flushPromises()
    const heads = w.findAll('th').map((h) => h.text())
    expect(heads).toContain('R1')
    expect(heads).toContain('R2')
    expect(heads).toContain('R3')
    expect(heads).not.toContain('Done')
  })

  it('one round needs no columns, just a tick box', async () => {
    withRounds(1)
    const w = mount(WorkoutPrintView)
    await flushPromises()
    const heads = w.findAll('th').map((h) => h.text())
    expect(heads).toContain('Done')
    expect(heads).not.toContain('R1')
  })

  it('prints one row per exercise however many rounds there are', async () => {
    // The complaint that started this: a two-round circuit read as duplicated
    // rows. Row count must not scale with rounds.
    withRounds(1)
    const one = mount(WorkoutPrintView)
    await flushPromises()
    const rowsAtOne = one.findAll('tbody tr').length

    withRounds(4)
    const four = mount(WorkoutPrintView)
    await flushPromises()
    expect(four.findAll('tbody tr').length).toBe(rowsAtOne)
  })
})

describe('WorkoutPrintView circuits (SB-528)', () => {
  // Gabe's Monday shape, now that SB-527 makes it data: Circuit A twice with a
  // four-minute water break, then Circuit B once.
  const blocks = [
    { id: 'bA', template_id: 't1', label: 'Circuit A', position: 0, rounds: 2, rest_after_seconds: 240 },
    { id: 'bB', template_id: 't1', label: 'Circuit B', position: 1, rounds: 1, rest_after_seconds: null },
  ]
  const items = [
    { id: 'w', exercise_key: 'easy_jog', section: 'warmup', position: 0, block_id: null, target_distance_m: 804, target_reps: null, target_duration_seconds: null, target_load_kg: null, rest_seconds: null, variant: null, notes: null },
    { id: 'a1', exercise_key: 'interval_run', section: 'main', position: 1, block_id: 'bA', target_duration_seconds: 60, target_reps: null, target_load_kg: null, target_distance_m: null, rest_seconds: null, variant: 'left', notes: null },
    { id: 'a2', exercise_key: 'interval_run', section: 'main', position: 2, block_id: 'bA', target_duration_seconds: 60, target_reps: null, target_load_kg: null, target_distance_m: null, rest_seconds: null, variant: 'right', notes: null },
    { id: 'b1', exercise_key: 'easy_jog', section: 'main', position: 3, block_id: 'bB', target_duration_seconds: 60, target_reps: null, target_load_kg: null, target_distance_m: null, rest_seconds: null, variant: null, notes: null },
  ]

  const render = async () => {
    apiCallMock.mockReset()
    apiCallMock.mockImplementation((path: string) => {
      if (path.startsWith('/workouts/templates/'))
        return Promise.resolve({ ...template, rounds: 1, blocks, items })
      if (path.startsWith('/athletes/')) return Promise.resolve({ id: 'a1', display_name: 'Gabe' })
      if (path === '/workouts/exercises') return Promise.resolve(exercises)
      return Promise.reject(new Error(`unexpected: ${path}`))
    })
    const w = mount(WorkoutPrintView)
    await flushPromises()
    return w
  }

  it('heads each circuit with its own round count', async () => {
    const w = await render()
    const bars = w.findAll('[data-testid="circuit-bar"]').map((b) => b.text())
    expect(bars[0]).toContain('CIRCUIT A')
    expect(bars[0]).toContain('COMPLETE 2 ROUNDS')
    expect(bars[1]).toContain('CIRCUIT B')
    // One round is the default; saying so would be noise.
    expect(bars[1]).not.toContain('ROUNDS')
  })

  it('gives each circuit its own columns, since their rounds differ', async () => {
    // The reason a circuit gets its own table: A needs R1/R2, B needs neither.
    const w = await render()
    const tables = w.findAll('table.sheet-table')
    const heads = tables.map((t) => t.findAll('th').map((h) => h.text()))
    expect(heads[1]).toContain('R1')
    expect(heads[1]).toContain('R2')
    expect(heads[2]).toContain('Done')
    expect(heads[2]).not.toContain('R1')
  })

  it('renders rest as a row in the sequence, not a note on the last exercise', async () => {
    const w = await render()
    const rest = w.get('[data-testid="rest-row"]')
    expect(rest.text()).toContain('Rest')
    expect(rest.text()).toContain('4:00')
    expect(rest.text()).toContain('water')
  })

  it('marks left and right as the distinct movements they are', async () => {
    const w = await render()
    expect(w.text()).toContain('(L)')
    expect(w.text()).toContain('(R)')
  })

  it('keeps the warm-up out of any circuit', async () => {
    const w = await render()
    // Three tables: loose warm-up, Circuit A, Circuit B.
    expect(w.findAll('table.sheet-table')).toHaveLength(3)
    expect(w.findAll('[data-testid="circuit-bar"]')).toHaveLength(2)
  })

  it('no longer prints a fold line', async () => {
    const w = await render()
    expect(w.text()).not.toContain('fold here')
  })
})
