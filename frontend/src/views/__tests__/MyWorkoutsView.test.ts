import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const apiCallMock = vi.fn()
vi.mock('@/config/api', () => ({ apiCall: (...a: unknown[]) => apiCallMock(...a) }))

const myAthlete: { value: unknown } = { value: null }
const loadMyAthlete = vi.fn(async () => {})
vi.mock('@/composables/useCoach', () => ({
  useMyAthlete: () => ({ myAthlete, loadMyAthlete }),
}))

const replaceMock = vi.fn()
const pushMock = vi.fn()
// The view now links to the build/log/print surfaces (SB-486), so the mock has
// to provide RouterLink as well as the router itself.
vi.mock('vue-router', () => ({
  useRouter: () => ({ replace: replaceMock, push: pushMock }),
  // `to` is forwarded so tests can assert where a link actually goes.
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import MyWorkoutsView from '../MyWorkoutsView.vue'

const template = {
  id: 't1',
  user_id: 'coach',
  athlete_id: 'a1',
  created_by: 'coach',
  name: 'Monday At-Home',
  type: 'circuit',
  rounds: 1,
  source: 'Matthew',
  notes: null,
  items: [],
  created_at: '2026-07-20T00:00:00Z',
}

/** Today in the athlete's own zone — the view compares date-only strings. */
const todayISO = (): string => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const daysFromNow = (n: number): string => {
  const d = new Date()
  d.setDate(d.getDate() + n)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/**
 * Serve the calls the athlete's home makes. Everything defaults to empty, so
 * each test names only the data it is about.
 */
const serve = (
  opts: {
    templates?: unknown[]
    sessions?: unknown[]
    schedule?: unknown[]
    recurrence?: unknown[]
  } = {},
) => {
  apiCallMock.mockImplementation((path: string) => {
    if (path === '/me/workouts') return Promise.resolve(opts.templates ?? [])
    if (path === '/workouts/exercises') return Promise.resolve([])
    if (path.startsWith('/workouts/sessions')) return Promise.resolve(opts.sessions ?? [])
    if (path.startsWith('/workouts/recurrence')) return Promise.resolve(opts.recurrence ?? [])
    if (path.startsWith('/workouts/schedule')) return Promise.resolve(opts.schedule ?? [])
    return Promise.reject(new Error(`unexpected: ${path}`))
  })
}

/** A planned occasion, authored by the coach unless told otherwise (SB-534). */
const occasion = (o: Partial<Record<string, unknown>> = {}) => ({
  id: 'sch1',
  template_id: 't1',
  athlete_id: 'ath1',
  created_by: 'coach',
  scheduled_for: todayISO(),
  notes: null,
  ...o,
})

beforeEach(() => {
  apiCallMock.mockReset()
  loadMyAthlete.mockClear()
  replaceMock.mockClear()
  pushMock.mockClear()
  myAthlete.value = null
})

describe('MyWorkoutsView (SB-332)', () => {
  // Being nobody's athlete used to bounce you to the dashboard, which made
  // training something only a coach's creation could record — including the
  // workout-count goal every user can set (SB-578).
  it('lets a user who is nobody’s athlete use the screen', async () => {
    myAthlete.value = null
    serve({ templates: [{ ...template, athlete_id: null, created_by: null }] })
    const w = mount(MyWorkoutsView)
    await flushPromises()

    expect(replaceMock).not.toHaveBeenCalled()
    expect(w.find('[data-testid="log-adhoc"]').exists()).toBe(true)
    await w.get('[data-testid="tab-plans"]').trigger('click')
    expect(w.text()).toContain('Monday At-Home')
  })

  it('sends no act-as header when the workouts are the user’s own', async () => {
    myAthlete.value = null
    serve()
    mount(MyWorkoutsView)
    await flushPromises()

    // An athlete id it does not have must not be invented — omitting the header
    // is what tells the API the rows are the caller's own.
    for (const [, opts] of apiCallMock.mock.calls) {
      const headers = (opts as { headers?: Record<string, string> } | undefined)?.headers ?? {}
      expect(headers['X-Act-As-Athlete']).toBeUndefined()
    }
  })

  it('calls a self-owned plan mine, not the coach’s', async () => {
    // Nothing in the list can belong to anyone else, so authorship needs no
    // comparison — and created_by is null on a self-owned row anyway.
    myAthlete.value = null
    serve({ templates: [{ ...template, athlete_id: null, created_by: null }] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')
    expect(w.text()).toContain('Mine')
    expect(w.text()).not.toContain('From my coach')
  })

  it('renders assigned workouts for a linked athlete', async () => {
    myAthlete.value = { id: 'a1', display_name: 'Gabe' }
    serve({ templates: [template] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    // Plans is where the plans live now (SB-530).
    await w.get('[data-testid="tab-plans"]').trigger('click')
    expect(w.text()).toContain('Monday At-Home')
    expect(w.text()).toContain('Coached by Matthew')
    expect(replaceMock).not.toHaveBeenCalled()
  })

  it('shows the empty state when nothing is assigned', async () => {
    myAthlete.value = { id: 'a1', display_name: 'Gabe' }
    serve()
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')
    expect(w.text()).toContain('No workouts yet')
  })
})

describe('MyWorkoutsView — ad-hoc entry (SB-531)', () => {
  it('offers logging a workout with no plan behind it', async () => {
    myAthlete.value = { id: 'ath1', linked_user_id: 'u1' }
    serve()
    const w = mount(MyWorkoutsView)
    await flushPromises()
    const link = w.get('[data-testid="log-adhoc"]')
    expect(link.attributes('href')).toBe('/my/workouts/log')
    expect(w.text()).toContain('Did a workout on your own?')
  })

  it('demotes building a plan — it was the loudest control and the wrong verb', async () => {
    myAthlete.value = { id: 'ath1', linked_user_id: 'u1' }
    serve()
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')
    expect(w.text()).toContain('+ Build a workout')
    expect(w.text()).not.toContain('+ New workout')
  })
})

describe('MyWorkoutsView — Training | Plans tabs (SB-530)', () => {
  beforeEach(() => {
    myAthlete.value = { id: 'ath1', linked_user_id: 'u1' }
  })

  it('opens on Training, where building a plan is not offered at all', async () => {
    serve({ templates: [template] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    // The reported confusion was two verbs competing for one button; the split
    // is only worth anything if "+ Build" is absent from the doing screen.
    expect(w.text()).not.toContain('+ Build a workout')
    expect(w.get('[data-testid="tab-training"]').attributes('aria-selected')).toBe('true')
  })

  it('keeps building on Plans and nowhere else', async () => {
    serve({ templates: [template] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.find('[data-testid="build-workout"]').exists()).toBe(false)
    await w.get('[data-testid="tab-plans"]').trigger('click')
    expect(w.get('[data-testid="build-workout"]').attributes('href')).toBe('/my/workouts/build')
  })

  it('points at the plans from Training while nothing is scheduled', async () => {
    // Otherwise the plans are a tab away with nothing saying so, which is the
    // same "built but no door" failure the split is meant to end.
    serve({ templates: [template] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    const jump = w.get('[data-testid="go-to-plans"]')
    expect(jump.text()).toContain('Or start one of your 1 plans')
    await jump.trigger('click')
    expect(w.get('[data-testid="tab-plans"]').attributes('aria-selected')).toBe('true')
    expect(w.find('[data-testid="build-workout"]').exists()).toBe(true)
  })

  it('does not send you to the plans when one is already due', async () => {
    serve({ templates: [template], schedule: [occasion()] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.find('[data-testid="go-to-plans"]').exists()).toBe(false)
  })

  it('loads the athlete\'s own sessions with the act-as header', async () => {
    serve()
    mount(MyWorkoutsView)
    await flushPromises()
    const call = apiCallMock.mock.calls.find((c) => String(c[0]).startsWith('/workouts/sessions'))
    expect(call).toBeDefined()
    expect((call![1] as { headers: Record<string, string> }).headers).toEqual({
      'X-Act-As-Athlete': 'ath1',
    })
  })
})

describe('MyWorkoutsView — Completed (SB-530)', () => {
  beforeEach(() => {
    myAthlete.value = { id: 'ath1', linked_user_id: 'u1' }
  })

  it('counts what has been done and says what each session logged', async () => {
    serve({
      templates: [template],
      sessions: [
        {
          id: 's1',
          template_id: 't1',
          session_date: daysFromNow(-1),
          type: 'circuit',
          sets: [],
          exercise_count: 22,
        },
      ],
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    // The count is the reward, and the row has to say what it was.
    expect(w.text()).toContain('Completed (1)')
    expect(w.text()).toContain('Monday At-Home')
    expect(w.text()).toContain('22 exercises logged')
  })

  it('marks an ad-hoc session "my own" without demoting it', async () => {
    serve({
      templates: [template],
      sessions: [
        {
          id: 's1',
          template_id: null,
          session_date: daysFromNow(-1),
          type: 'circuit',
          sets: [],
          exercise_count: 4,
        },
        {
          id: 's2',
          template_id: 't1',
          session_date: daysFromNow(-2),
          type: 'circuit',
          sets: [],
          exercise_count: 12,
        },
      ],
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    const [adhoc, coached] = w.findAll('[data-testid="completed-row"]')
    expect(adhoc.text()).toContain('4 exercises · my own')
    expect(coached.text()).toContain('12 exercises logged')
    // Noted, not demoted: it gets the same row treatment as the coach's.
    expect(adhoc.classes()).toEqual(coached.classes())
  })

  it('says so honestly when nothing has been logged', async () => {
    serve({ templates: [template] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.text()).toContain('Completed (0)')
    expect(w.find('[data-testid="completed-empty"]').exists()).toBe(true)
  })

  it('previews four and offers the rest behind "See all"', async () => {
    serve({
      sessions: Array.from({ length: 6 }, (_, i) => ({
        id: `s${i}`,
        template_id: null,
        session_date: daysFromNow(-i - 1),
        type: 'circuit',
        sets: [],
        exercise_count: 3,
      })),
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.findAll('[data-testid="completed-row"]')).toHaveLength(4)
    await w.get('[data-testid="see-all-completed"]').trigger('click')
    expect(w.findAll('[data-testid="completed-row"]')).toHaveLength(6)
  })
})

describe('MyWorkoutsView — session names (SB-536)', () => {
  beforeEach(() => {
    myAthlete.value = { id: 'ath1', linked_user_id: 'u1' }
  })

  const adhoc = (o: Partial<Record<string, unknown>> = {}) => ({
    id: 's1',
    template_id: null,
    session_date: daysFromNow(-1),
    type: 'circuit',
    name: null,
    sets: [],
    exercise_count: 4,
    ...o,
  })

  it('calls a session what the athlete called it', async () => {
    serve({ sessions: [adhoc({ name: 'Garage circuit' })] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.get('[data-testid="completed-row"]').text()).toContain('Garage circuit')
  })

  it('falls back to the plan name, then to the kind of workout', async () => {
    // Sessions logged before naming existed have no name and must still read.
    serve({
      templates: [template],
      sessions: [adhoc({ id: 's1', template_id: 't1' }), adhoc({ id: 's2' })],
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    const rows = w.findAll('[data-testid="completed-row"]')
    expect(rows.map((r) => r.text()).join(' ')).toContain('Monday At-Home')
    expect(rows.map((r) => r.text()).join(' ')).toContain('Circuit')
  })

  it('renames one from the list, keeping what was logged', async () => {
    serve({ sessions: [adhoc({ name: 'Sunday 1 Aug' })] })
    const w = mount(MyWorkoutsView)
    await flushPromises()

    await w.get('[data-testid="rename-open"]').trigger('click')
    await w.get('[data-testid="rename-input"]').setValue('Garage circuit')
    await w.get('[data-testid="rename-save"]').trigger('click')
    await flushPromises()

    const patch = apiCallMock.mock.calls.find(
      (c) => c[1] && (c[1] as { method?: string }).method === 'PATCH',
    )
    expect(String(patch![0])).toBe('/workouts/sessions/s1')
    // Only the name — the sets are the record, not a label on it.
    expect(JSON.parse((patch![1] as { body: string }).body)).toEqual({ name: 'Garage circuit' })
    expect(w.get('[data-testid="completed-row"]').text()).toContain('Garage circuit')
  })

  it('clearing the name falls back to the date rather than to nothing', async () => {
    serve({ sessions: [adhoc({ name: 'Garage circuit', session_date: '2026-08-02' })] })
    const w = mount(MyWorkoutsView)
    await flushPromises()

    await w.get('[data-testid="rename-open"]').trigger('click')
    await w.get('[data-testid="rename-input"]').setValue('   ')
    await w.get('[data-testid="rename-save"]').trigger('click')
    await flushPromises()

    const patch = apiCallMock.mock.calls.find(
      (c) => c[1] && (c[1] as { method?: string }).method === 'PATCH',
    )
    expect(JSON.parse((patch![1] as { body: string }).body)).toEqual({ name: 'Sunday 2 Aug' })
  })

  it('offers no rename on a session logged against a plan', async () => {
    // That one is called what the coach called the workout.
    serve({ templates: [template], sessions: [adhoc({ template_id: 't1' })] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.find('[data-testid="rename-open"]').exists()).toBe(false)
  })
})

describe('MyWorkoutsView — Coming up (SB-530, SB-534)', () => {
  beforeEach(() => {
    myAthlete.value = { id: 'ath1', linked_user_id: 'u1' }
  })

  it('is absent entirely while nothing is scheduled', async () => {
    serve({ templates: [template] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.find('[data-testid="coming-up"]').exists()).toBe(false)
    expect(w.find('[data-testid="start-card"]').exists()).toBe(false)
  })

  it('promotes the workout due today to a labelled Start card', async () => {
    serve({
      templates: [template, { ...template, id: 't2', name: 'Track Thursday' }],
      schedule: [
        occasion(),
        occasion({ id: 'sch2', template_id: 't2', scheduled_for: daysFromNow(3) }),
      ],
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    const card = w.get('[data-testid="start-card"]')
    expect(card.text()).toContain('Monday At-Home')
    expect(card.text()).toContain('Today')
    await card.get('[data-testid="start-workout"]').trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/my/workouts/log/t1')
    // The one still ahead stays in Coming up rather than doubling up.
    const coming = w.get('[data-testid="coming-up"]')
    expect(coming.text()).toContain('Track Thursday')
    expect(coming.text()).not.toContain('Monday At-Home')
  })

  it('drops the ad-hoc entry to a quiet line when something is due', async () => {
    serve({ templates: [template], schedule: [occasion()] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    const adhoc = w.get('[data-testid="log-adhoc"]')
    expect(adhoc.text()).toContain('+ Log something I just did')
    expect(adhoc.attributes('href')).toBe('/my/workouts/log')
  })

  it('names what is next when nothing is due today', async () => {
    serve({
      templates: [{ ...template, name: 'Track Thursday' }],
      schedule: [occasion({ scheduled_for: daysFromNow(3) })],
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.text()).toContain('Nothing scheduled today')
    expect(w.text()).toContain('Next up: Track Thursday')
    // Logging is still the primary control when nothing is due.
    expect(w.get('[data-testid="log-adhoc"]').text()).toContain('+ Log a workout')
  })

  it('ignores a day that has already passed', async () => {
    serve({ templates: [template], schedule: [occasion({ scheduled_for: daysFromNow(-2) })] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.find('[data-testid="start-card"]').exists()).toBe(false)
    expect(w.find('[data-testid="coming-up"]').exists()).toBe(false)
  })

  it('asks only for occasions from today forward', async () => {
    serve({ templates: [template] })
    mount(MyWorkoutsView)
    await flushPromises()
    const call = apiCallMock.mock.calls.find((c) => String(c[0]).startsWith('/workouts/schedule'))
    expect(String(call![0])).toContain(`date_from=${todayISO()}`)
    expect((call![1] as { headers: Record<string, string> }).headers).toEqual({
      'X-Act-As-Athlete': 'ath1',
    })
  })

  it('drops an occasion whose plan has since been deleted', async () => {
    // Otherwise it renders as a row with no name on it.
    serve({
      templates: [template],
      schedule: [
        occasion({ id: 'gone', template_id: 'deleted', scheduled_for: daysFromNow(2) }),
        occasion({ id: 'ok', template_id: 't1', scheduled_for: daysFromNow(3) }),
      ],
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    const rows = w.findAll('[data-testid="coming-up-row"]')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('Monday At-Home')
  })
})

describe('MyWorkoutsView — who scheduled it (SB-534)', () => {
  beforeEach(() => {
    myAthlete.value = { id: 'ath1', linked_user_id: 'u1' }
  })

  it('says the coach put it there', async () => {
    serve({ templates: [template], schedule: [occasion({ created_by: 'coach' })] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    // A workout Matthew expects of him reads differently from one he planned.
    expect(w.get('[data-testid="scheduled-by"]').text()).toBe('From Matthew')
  })

  it('says when the athlete put it there themselves', async () => {
    serve({ templates: [template], schedule: [occasion({ created_by: 'u1' })] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.get('[data-testid="scheduled-by"]').text()).toBe('Mine')
  })

  it('offers to unschedule only what the athlete scheduled', async () => {
    serve({
      templates: [template, { ...template, id: 't2', name: 'Track Thursday' }],
      schedule: [
        occasion({ id: 'sch1', created_by: 'coach', scheduled_for: daysFromNow(2) }),
        occasion({ id: 'sch2', template_id: 't2', created_by: 'u1', scheduled_for: daysFromNow(3) }),
      ],
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    const rows = w.findAll('[data-testid="coming-up-row"]')
    // Matthew's Thursday is not Gabe's to remove — the API says so too.
    expect(rows[0].find('[data-testid="unschedule"]').exists()).toBe(false)
    expect(rows[1].find('[data-testid="unschedule"]').exists()).toBe(true)

    await rows[1].get('[data-testid="unschedule"]').trigger('click')
    await flushPromises()
    const del = apiCallMock.mock.calls.find((c) => c[1] && (c[1] as { method?: string }).method === 'DELETE')
    expect(String(del![0])).toBe('/workouts/schedule/sch2')
  })

  it('lets the athlete put a plan on a day from the Plans tab', async () => {
    serve({ templates: [template] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')

    await w.get('[data-testid="schedule-open"]').trigger('click')
    await w.get('[data-testid="schedule-date"]').setValue(daysFromNow(2))
    await w.get('[data-testid="schedule-save"]').trigger('click')
    await flushPromises()

    const post = apiCallMock.mock.calls.find((c) => c[1] && (c[1] as { method?: string }).method === 'POST')
    expect(String(post![0])).toBe('/workouts/schedule')
    expect(JSON.parse((post![1] as { body: string }).body)).toEqual({
      template_id: 't1',
      scheduled_for: daysFromNow(2),
    })
    // Scheduling for yourself goes through the same act-as header the coach uses.
    expect((post![1] as { headers: Record<string, string> }).headers).toEqual({
      'X-Act-As-Athlete': 'ath1',
    })
  })
})

describe('MyWorkoutsView — Plans grouping (SB-530)', () => {
  beforeEach(() => {
    myAthlete.value = { id: 'ath1', linked_user_id: 'u1' }
  })

  it('separates the coach\'s plans from the athlete\'s own', async () => {
    serve({
      templates: [
        { ...template, session_count: 5 },
        {
          ...template,
          id: 't2',
          name: 'Saturday garage circuit',
          created_by: 'u1',
          source: null,
          session_count: 0,
        },
      ],
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')

    const fromCoach = w.get('[data-testid="group-from-coach"]')
    expect(fromCoach.text()).toContain('From Matthew')
    expect(fromCoach.text()).toContain('Monday At-Home')
    expect(fromCoach.text()).not.toContain('Saturday garage circuit')

    const mine = w.get('[data-testid="group-mine"]')
    expect(mine.text()).toContain('Saturday garage circuit')
    // Athlete-authored workouts shipped and nobody found them (SB-486); the
    // empty prompt only belongs on an account that has none.
    expect(w.find('[data-testid="mine-empty"]').exists()).toBe(false)
  })

  it('shows how often each plan has been done', async () => {
    serve({ templates: [{ ...template, session_count: 5 }, { ...template, id: 't2', name: 'Speed Endurance', session_count: 0 }] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')
    const counts = w.findAll('[data-testid="usage-count"]').map((n) => n.text())
    expect(counts).toContain('done 5×')
    expect(counts).toContain('not yet')
  })

  it('offers a labelled Start workout on every plan, not an icon tooltip', async () => {
    serve({ templates: [template] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')
    // The old control was an unlabelled icon with a `title`, which does not
    // exist on touch — the most frequent action was the least visible one.
    expect(w.find('[data-testid="log-this"]').exists()).toBe(false)
    await w.get('[data-testid="start-workout"]').trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/my/workouts/log/t1')
  })

  it('prompts an athlete who has authored nothing to build something', async () => {
    serve({ templates: [template] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')
    expect(w.find('[data-testid="group-mine"]').exists()).toBe(false)
    expect(w.get('[data-testid="mine-empty"]').text()).toContain('Made something up at practice?')
  })

  it('falls back to a generic coach label when the plans disagree on authorship', async () => {
    serve({
      templates: [template, { ...template, id: 't2', name: 'Bike day', source: 'Coach Dana' }],
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')
    expect(w.get('[data-testid="group-from-coach"]').text()).toContain('From my coach')
  })
})


describe('MyWorkoutsView — a week that repeats (SB-535)', () => {
  beforeEach(() => {
    myAthlete.value = { id: 'ath1', linked_user_id: 'u1' }
  })

  const rule = (o: Partial<Record<string, unknown>> = {}) => ({
    id: 'r1',
    template_id: 't1',
    athlete_id: 'ath1',
    created_by: 'coach',
    byweekday: [1, 4],
    starts_on: '2026-08-03',
    ends_on: null,
    active: true,
    generated_through: null,
    ...o,
  })

  it('says what repeats, on the plan it belongs to', async () => {
    serve({ templates: [template], recurrence: [rule()] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')
    expect(w.get('[data-testid="repeat-line"]').text()).toContain('Every Mon, Thu')
  })

  it('shows nothing for a plan that does not repeat', async () => {
    serve({ templates: [template] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')
    expect(w.find('[data-testid="repeat-line"]').exists()).toBe(false)
  })

  it('ignores a pattern that has been turned off', async () => {
    serve({ templates: [template], recurrence: [rule({ active: false })] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')
    expect(w.find('[data-testid="repeat-line"]').exists()).toBe(false)
  })

  it('stops a repeat by turning it off, not by deleting it', async () => {
    // Future occasions stop; the ones already on the calendar stay, along with
    // anything logged against them.
    serve({ templates: [template], recurrence: [rule()] })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    await w.get('[data-testid="tab-plans"]').trigger('click')
    await w.get('[data-testid="repeat-stop"]').trigger('click')
    await flushPromises()

    const patch = apiCallMock.mock.calls.find(
      (c) => c[1] && (c[1] as { method?: string }).method === 'PATCH',
    )
    expect(String(patch![0])).toBe('/workouts/recurrence/r1')
    expect(JSON.parse((patch![1] as { body: string }).body)).toEqual({ active: false })
    expect(
      apiCallMock.mock.calls.some((c) => c[1] && (c[1] as { method?: string }).method === 'DELETE'),
    ).toBe(false)
  })

  it('a generated occasion reads exactly like a hand-scheduled one', async () => {
    // Coming up is fed by occasions; nothing there branches on where they came
    // from, which is the point of generating into the same table.
    serve({
      templates: [template],
      recurrence: [rule()],
      schedule: [
        {
          id: 'sch1',
          template_id: 't1',
          athlete_id: 'ath1',
          created_by: 'coach',
          scheduled_for: daysFromNow(2),
          notes: null,
          recurrence_id: 'r1',
        },
      ],
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    const row = w.get('[data-testid="coming-up-row"]')
    expect(row.text()).toContain('Monday At-Home')
    expect(row.get('[data-testid="scheduled-by"]').text()).toBe('From Matthew')
  })
})
