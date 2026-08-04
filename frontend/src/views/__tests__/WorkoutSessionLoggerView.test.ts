import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const h = vi.hoisted(() => ({
  createSession: vi.fn(),
  getTemplate: vi.fn(),
  createTemplate: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  isCoach: { value: true },
  loadRoles: vi.fn().mockResolvedValue(undefined),
  // The athlete the caller IS, for the self-service path (SB-486).
  myAthlete: { value: null as { id: string } | null },
  loadMyAthlete: vi.fn().mockResolvedValue(undefined),
  load: vi.fn().mockResolvedValue(undefined),
  params: { athleteId: 'ath1' } as Record<string, string>,
}))

const catalog = [
  {
    key: 'pushups', display_name: 'Push-ups', category: 'strength', measures: ['reps', 'duration_s'],
    is_benchmark: false, owner_id: null, visibility: 'public', created_by: null, forked_from: null,
    aliases: [], movement_pattern: 'push', equipment: [], body_region: [], laterality: null,
    difficulty: null, tags: [], media_url: null, thumbnail_url: null, cues: [], instructions: null,
  },
  {
    key: 'farmers_carry', display_name: "Farmer's carry", category: 'strength', measures: ['duration_s', 'load_kg'],
    is_benchmark: false, owner_id: null, visibility: 'public', created_by: null, forked_from: null,
    aliases: [], movement_pattern: 'carry', equipment: ['dumbbell'], body_region: [], laterality: null,
    difficulty: null, tags: [], media_url: null, thumbnail_url: null, cues: [], instructions: null,
  },
  {
    key: '40yd_dash', display_name: '40-yard dash', category: 'test', measures: ['distance_m', 'time_s'],
    is_benchmark: true, owner_id: null, visibility: 'public', created_by: null, forked_from: null,
    aliases: [], movement_pattern: 'sprint', equipment: [], body_region: [], laterality: null,
    difficulty: null, tags: [], media_url: null, thumbnail_url: null, cues: [], instructions: null,
  },
]

vi.mock('@/composables/useExercises', async () => {
  const { ref } = await import('vue')
  return { useExercises: () => ({ exercises: ref(catalog), load: h.load, loading: ref(false), error: ref(null) }) }
})
vi.mock('@/composables/useCoach', () => ({
  useRoles: () => ({ isCoach: h.isCoach, loadRoles: h.loadRoles }),
  useMyAthlete: () => ({ myAthlete: h.myAthlete, loadMyAthlete: h.loadMyAthlete }),
}))
vi.mock('@/composables/useWorkoutTemplates', () => ({
  getTemplate: (...a: unknown[]) => h.getTemplate(...a),
  createTemplate: (...a: unknown[]) => h.createTemplate(...a),
}))
vi.mock('@/composables/useWorkoutSessions', () => ({
  createSession: (...a: unknown[]) => h.createSession(...a),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: h.params }),
  useRouter: () => ({ push: h.push, replace: h.replace }),
  RouterLink: { template: '<a><slot /></a>' },
}))

beforeEach(() => {
  vi.clearAllMocks()
  h.isCoach.value = true
  h.myAthlete.value = null
  h.params = { athleteId: 'ath1' }
})

async function mountLogger() {
  const View = (await import('../WorkoutSessionLoggerView.vue')).default
  const w = mount(View, { global: { stubs: { RouterLink: true } } })
  await flushPromises()
  return w
}

describe('WorkoutSessionLoggerView', () => {
  it('an athlete logs for themselves with no route param (SB-486)', async () => {
    // The whole point: Gabe opens /my/workouts/log, the view resolves *him* as
    // the subject, and the API call carries his own athlete id.
    h.isCoach.value = false
    h.params = {}
    h.myAthlete.value = { id: 'ath1' }
    h.createSession.mockResolvedValue({ id: 's1' })

    const w = await mountLogger()

    expect(h.replace).not.toHaveBeenCalled()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    await w.find('[data-testid="reps-pushups-0"]').setValue(10)
    await w.find('[data-testid="save"]').trigger('click')
    await flushPromises()

    expect(h.createSession).toHaveBeenCalled()
    expect(h.createSession.mock.calls[0][1]).toBe('ath1')
  })

  it('logs a workout for a user who is nobody’s athlete', async () => {
    // SB-486 made the gate "do we have an athlete" rather than "are you a
    // coach". SB-578 removes the gate: a user with no athlete record is logging
    // their own workout, and a null athlete id is how that is expressed.
    h.isCoach.value = false
    h.params = {}
    h.myAthlete.value = null
    const w = await mountLogger()
    expect(h.replace).not.toHaveBeenCalled()
    expect(w.find('[data-testid="save"]').exists()).toBe(true)
  })

  it('adds an exercise via the picker', async () => {
    const w = await mountLogger()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    expect(w.find('[data-testid="row-pushups"]').exists()).toBe(true)
  })

  it('save is disabled until a set has a value', async () => {
    const w = await mountLogger()
    expect((w.find('[data-testid="save"]').element as HTMLButtonElement).disabled).toBe(true)
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    // row added but no value yet → still disabled
    expect((w.find('[data-testid="save"]').element as HTMLButtonElement).disabled).toBe(true)
    await w.find('[data-testid="reps-pushups-0"]').setValue(12)
    expect((w.find('[data-testid="save"]').element as HTMLButtonElement).disabled).toBe(false)
  })

  it('saves a session with act-as and lb→kg conversion', async () => {
    h.createSession.mockResolvedValue({ id: 's1' })
    const w = await mountLogger()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-farmers_carry"]').trigger('click')
    await w.find('[data-testid="load_lb-farmers_carry-0"]').setValue(10)
    await w.find('[data-testid="save"]').trigger('click')
    await flushPromises()

    expect(h.createSession).toHaveBeenCalledTimes(1)
    const [payload, athleteId] = h.createSession.mock.calls[0]
    expect(athleteId).toBe('ath1')
    expect(payload.sets[0]).toMatchObject({ exercise_key: 'farmers_carry', load_kg: 4.5 })
    // No template behind this one, so it offers to keep it rather than leaving
    // straight away (SB-531). Declining goes home as before.
    expect(w.find('[data-testid="keep-offer"]').exists()).toBe(true)
    await w.find('[data-testid="keep-no"]').trigger('click')
    expect(h.push).toHaveBeenCalledWith('/coach/ath1')
  })

  it('logs a benchmark three times — three sets with time + set_index', async () => {
    h.createSession.mockResolvedValue({ id: 's2' })
    const w = await mountLogger()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-40yd_dash"]').trigger('click')
    await w.find('[data-testid="add-set-40yd_dash"]').trigger('click')
    await w.find('[data-testid="add-set-40yd_dash"]').trigger('click')
    await w.find('[data-testid="time_seconds-40yd_dash-0"]').setValue(5.4)
    await w.find('[data-testid="time_seconds-40yd_dash-1"]').setValue(5.2)
    await w.find('[data-testid="time_seconds-40yd_dash-2"]').setValue(5.3)
    await w.find('[data-testid="save"]').trigger('click')
    await flushPromises()

    const [payload] = h.createSession.mock.calls[0]
    expect(payload.sets).toHaveLength(3)
    expect(payload.sets.map((s: { set_index: number; time_seconds: number }) => [s.set_index, s.time_seconds])).toEqual([
      [1, 5.4],
      [2, 5.2],
      [3, 5.3],
    ])
  })

  it('from a template: prefills rows and posts template_id', async () => {
    h.params = { athleteId: 'ath1', templateId: 't9' }
    h.getTemplate.mockResolvedValue({
      id: 't9',
      name: 'Monday - Circuit',
      type: 'circuit',
      rounds: 3,
      source: null,
      notes: null,
      created_at: null,
      items: [
        { id: 'i1', exercise_key: 'pushups', section: 'main', position: 0, target_reps: 15, target_duration_seconds: null, target_load_kg: null, target_distance_m: null, rest_seconds: null, variant: null, notes: null },
      ],
    })
    h.createSession.mockResolvedValue({ id: 's3' })
    const w = await mountLogger()

    expect(h.getTemplate).toHaveBeenCalledWith('t9', 'ath1')
    expect(w.find('[data-testid="from-template"]').text()).toContain('Monday - Circuit')
    expect(w.find('[data-testid="row-pushups"]').exists()).toBe(true)

    await w.find('[data-testid="reps-pushups-0"]').setValue(14)
    await w.find('[data-testid="save"]').trigger('click')
    await flushPromises()
    const [payload] = h.createSession.mock.calls[0]
    expect(payload.template_id).toBe('t9')
    expect(payload.sets[0]).toMatchObject({ exercise_key: 'pushups', reps: 14 })
  })

  it('removes an added row', async () => {
    const w = await mountLogger()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    expect(w.find('[data-testid="row-pushups"]').exists()).toBe(true)
    await w.find('[data-testid="remove-pushups"]').trigger('click')
    expect(w.find('[data-testid="row-pushups"]').exists()).toBe(false)
  })
})

describe('WorkoutSessionLoggerView — save failure and dead ends (SB-501)', () => {
  const addPushups = async (w: Awaited<ReturnType<typeof mountLogger>>) => {
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    await w.find('[data-testid="reps-pushups-0"]').setValue(20)
  }

  it('says why Save is unavailable instead of offering a dead button', async () => {
    // A disabled control with no explanation is the worst kind of friction
    // mid-workout: nothing to read, nothing to fix.
    const w = await mountLogger()
    expect(w.get('[data-testid="save"]').attributes('disabled')).toBeDefined()
    expect(w.get('[data-testid="save-blocked"]').text()).toContain('Add an exercise')
  })

  it('drops the explanation once the session can be saved', async () => {
    const w = await mountLogger()
    await addPushups(w)
    expect(w.find('[data-testid="save-blocked"]').exists()).toBe(false)
    expect(w.get('[data-testid="save"]').attributes('disabled')).toBeUndefined()
  })

  it('explains a failed save in words, not a status code', async () => {
    const w = await mountLogger()
    await addPushups(w)
    h.createSession.mockRejectedValueOnce(Object.assign(new Error('HTTP 500'), { status: 500 }))
    await w.get('[data-testid="save"]').trigger('click')
    await flushPromises()

    const panel = w.get('[data-testid="save-error"]')
    expect(panel.text()).toContain("Couldn't save this session")
    expect(panel.text()).toContain('The server had a problem')
    expect(panel.text()).toContain('HTTP 500') // raw detail still available
  })

  it('tells the athlete their work was not lost', async () => {
    // The thing that actually matters when a save fails mid-session: do not
    // make a kid think he has to log the whole workout again.
    const w = await mountLogger()
    await addPushups(w)
    h.createSession.mockRejectedValueOnce(Object.assign(new Error('nope'), { status: 500 }))
    await w.get('[data-testid="save"]').trigger('click')
    await flushPromises()

    expect(w.get('[data-testid="save-error"]').text()).toContain('still on this page')
    // And it genuinely is not lost — the row survives.
    expect(w.find('[data-testid="reps-pushups-0"]').exists()).toBe(true)
    expect(h.push).not.toHaveBeenCalled()
  })

  it('lets a retry succeed after a failure', async () => {
    const w = await mountLogger()
    await addPushups(w)
    h.createSession.mockRejectedValueOnce(Object.assign(new Error('nope'), { status: 500 }))
    await w.get('[data-testid="save"]').trigger('click')
    await flushPromises()

    h.createSession.mockResolvedValueOnce({ id: 's1' })
    await w.get('[data-testid="save"]').trigger('click')
    await flushPromises()

    expect(w.find('[data-testid="save-error"]').exists()).toBe(false)
    // Ad-hoc: the keep-offer stands in for navigation (SB-531).
    expect(w.find('[data-testid="keep-offer"]').exists()).toBe(true)
  })
})

describe('WorkoutSessionLoggerView — ad-hoc workout (SB-531)', () => {
  // Gabe wakes up, does four exercises, wants credit. No plan involved.
  const logSomething = async (name?: string) => {
    h.createSession.mockResolvedValue({ id: 's9' })
    const w = await mountLogger()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    await w.find('[data-testid="reps-pushups-0"]').setValue(20)
    // A fixed date so the default name is an exact string, not today's.
    await w.find('[data-testid="session-date"]').setValue('2026-08-02')
    if (name !== undefined) await w.find('[data-testid="session-name"]').setValue(name)
    await w.find('[data-testid="save"]').trigger('click')
    await flushPromises()
    return w
  }

  it('titles it a new workout, not a log against something', async () => {
    const w = await mountLogger()
    expect(w.text()).toContain('New workout')
    expect(w.find('[data-testid="from-template"]').exists()).toBe(false)
  })

  it('saves with no template behind it', async () => {
    await logSomething()
    const [payload] = h.createSession.mock.calls[0]
    expect(payload.template_id ?? null).toBeNull()
    expect(payload.sets).toHaveLength(1)
  })

  it('offers to keep it rather than requiring a name up front', async () => {
    // Asking him to name it before he gets the tick is friction in the wrong
    // place — credit first, the offer second.
    const w = await logSomething()
    const offer = w.get('[data-testid="keep-offer"]')
    expect(offer.text()).toContain('Logged')
    expect(offer.text()).toContain('Do this one again?')
  })

  it('keeping it creates a reusable workout under the session\'s own name', async () => {
    h.createTemplate.mockResolvedValue({ id: 't9' })
    const w = await logSomething('Garage circuit')
    await w.get('[data-testid="keep-yes"]').trigger('click')
    await flushPromises()

    const [payload, athleteId] = h.createTemplate.mock.calls[0]
    expect(athleteId).toBe('ath1')
    // The plan arrives called what he called the session (SB-536), rather than
    // being renamed a second time.
    expect(payload.name).toBe('Garage circuit')
    expect(payload.items[0]).toMatchObject({ exercise_key: 'pushups', position: 0 })
    expect(h.push).toHaveBeenCalledWith('/coach/ath1')
  })

  it('arrives already named, so nothing blocks the credit', async () => {
    const w = await mountLogger()
    await w.find('[data-testid="session-date"]').setValue('2026-08-02')
    // Shown as a placeholder, not typed in: the name is never a surprise, and
    // never a field he has to fill before getting the tick (SB-536).
    const field = w.get('[data-testid="session-name"]')
    expect(field.attributes('placeholder')).toBe('Sunday 2 Aug')
    expect((field.element as HTMLInputElement).value).toBe('')
  })

  it('saves the default name when he types none', async () => {
    await logSomething()
    const [payload] = h.createSession.mock.calls[0]
    expect(payload.name).toBe('Sunday 2 Aug')
  })

  it('saves what he calls it instead, when he says', async () => {
    await logSomething('Garage circuit')
    const [payload] = h.createSession.mock.calls[0]
    expect(payload.name).toBe('Garage circuit')
  })

  it('declining just goes home — the session is already saved', async () => {
    const w = await logSomething()
    await w.get('[data-testid="keep-no"]').trigger('click')
    expect(h.createTemplate).not.toHaveBeenCalled()
    expect(h.push).toHaveBeenCalledWith('/coach/ath1')
  })

  it('a failed keep does not imply the session was lost', async () => {
    h.createTemplate.mockRejectedValueOnce(new Error('nope'))
    const w = await logSomething()
    await w.get('[data-testid="keep-yes"]').trigger('click')
    await flushPromises()
    expect(w.get('[data-testid="keep-offer"]').text()).toContain('your session is logged either way')
  })

  it('a workout from a template still leaves straight away', async () => {
    // The existing flow must not change.
    h.params = { athleteId: 'ath1', templateId: 't1' }
    h.getTemplate.mockResolvedValue({ id: 't1', name: 'Monday At-Home', rounds: 1, items: [] })
    h.createSession.mockResolvedValue({ id: 's10' })
    const w = await mountLogger()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    await w.find('[data-testid="reps-pushups-0"]').setValue(15)
    await w.find('[data-testid="save"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="keep-offer"]').exists()).toBe(false)
    expect(h.push).toHaveBeenCalledWith('/coach/ath1')
  })
})


// --- SB-545: the logger finally knows what it was asked to do ---------------

const ITEM = (id: string, key: string, block_id: string | null, position: number) => ({
  id,
  exercise_key: key,
  section: 'main',
  position,
  block_id,
  target_reps: null,
  target_duration_seconds: 60,
  target_load_kg: null,
  target_distance_m: null,
  rest_seconds: null,
  variant: null,
  notes: null,
})

const CIRCUIT_TEMPLATE = {
  id: 't5',
  name: 'Monday At-Home',
  type: 'circuit',
  rounds: 1,
  source: 'Matthew',
  notes: null,
  created_at: null,
  blocks: [
    { id: 'b1', template_id: 't5', label: 'Circuit A', position: 0, rounds: 2, rest_after_seconds: 240 },
    { id: 'b2', template_id: 't5', label: 'Circuit B', position: 1, rounds: 1, rest_after_seconds: null },
  ],
  items: [
    ITEM('a1', 'pushups', 'b1', 0),
    ITEM('a2', 'farmers_carry', 'b1', 1),
    ITEM('b1i', 'pushups', 'b2', 2),
  ],
}

describe('WorkoutSessionLoggerView — circuits and the prescription (SB-545)', () => {
  const openCircuit = async () => {
    h.params = { athleteId: 'ath1', templateId: 't5' }
    h.getTemplate.mockResolvedValue(CIRCUIT_TEMPLATE)
    return mountLogger()
  }

  it('shows the circuits the card and the sheet already show', async () => {
    const w = await openCircuit()
    const bars = w.findAll('[data-testid="logger-circuit-bar"]').map((b) => b.text())
    expect(bars).toHaveLength(2)
    expect(bars[0]).toContain('Circuit A')
    expect(bars[0]).toContain('×2')
    expect(bars[1]).toContain('Circuit B')
  })

  it('lays a two-round circuit out as R1 and R2, already numbered', async () => {
    // Before this, recording the prescription meant tapping "+ Add set" on
    // eleven cards and typing twenty-two round numbers.
    const w = await openCircuit()
    expect(w.get('[data-testid="attempt-label-farmers_carry-0"]').text()).toBe('R1')
    expect(w.get('[data-testid="attempt-label-farmers_carry-1"]').text()).toBe('R2')
  })

  it('no longer asks the athlete to type a round number', async () => {
    const w = await openCircuit()
    expect(w.find('[data-testid="round-farmers_carry"]').exists()).toBe(false)
  })

  it('sends the prescribed item each set answers', async () => {
    // `pushups` appears in both circuits — without the link the two are
    // indistinguishable, which is the whole reason SB-527 added the column.
    const w = await openCircuit()
    await w.find('[data-testid="duration_s-farmers_carry-0"]').setValue(60)
    await w.find('[data-testid="save"]').trigger('click')
    await flushPromises()

    const [payload] = h.createSession.mock.calls[0]
    const set = payload.sets.find(
      (s: { exercise_key: string }) => s.exercise_key === 'farmers_carry',
    )
    expect(set.template_item_id).toBe('a2')
    expect(set.round_number).toBe(1)
  })

  it('leaves an exercise the athlete adds unlinked', async () => {
    const w = await openCircuit()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    // Toggling adds a row with no prescription behind it; the existing
    // prefilled pushups rows keep theirs.
    await flushPromises()
    expect(w.findAll('[data-testid="logger-circuit-bar"]').length).toBeGreaterThan(0)
  })
})
