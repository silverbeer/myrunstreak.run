import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WorkoutTemplateCard from '../WorkoutTemplateCard.vue'
import type { Exercise, TemplateItem, WorkoutTemplate } from '@/types/workout'

const ti = (over: Partial<TemplateItem>): TemplateItem => ({
  id: Math.random().toString(),
  exercise_key: 'x',
  section: 'main',
  position: 0,
  target_reps: null,
  target_duration_seconds: null,
  target_load_kg: null,
  target_distance_m: null,
  rest_seconds: null,
  variant: null,
  notes: null,
  ...over,
})

const template: WorkoutTemplate = {
  id: 't1',
  name: 'Monday - Circuit',
  type: 'circuit',
  rounds: 2,
  source: 'Matthew',
  notes: null,
  created_at: null,
  items: [
    ti({ exercise_key: 'easy_jog', section: 'warmup', position: 0, target_duration_seconds: 480 }),
    ti({ exercise_key: 'bicep_curl', section: 'main', position: 2, target_load_kg: 4.54, target_duration_seconds: 60 }),
    ti({ exercise_key: 'side_plank', section: 'main', position: 1, variant: 'left', target_duration_seconds: 60 }),
  ],
}

const exercises: Exercise[] = [
  { key: 'bicep_curl', display_name: 'Bicep curls', measures: [] } as unknown as Exercise,
]

describe('WorkoutTemplateCard', () => {
  it('renders name, type and rounds', () => {
    const w = mount(WorkoutTemplateCard, { props: { template } })
    expect(w.text()).toContain('Monday - Circuit')
    expect(w.text()).toContain('circuit')
    expect(w.text()).toContain('2 rounds')
  })

  it('groups items under section headings in canonical order', () => {
    const w = mount(WorkoutTemplateCard, { props: { template } })
    const text = w.text()
    expect(text).toContain('Warm-up')
    expect(text).toContain('Main')
    // warm-up heading appears before main
    expect(text.indexOf('Warm-up')).toBeLessThan(text.indexOf('Main'))
  })

  it('sorts items within a section by position', () => {
    const w = mount(WorkoutTemplateCard, { props: { template } })
    const text = w.text()
    // side_plank (pos 1) before bicep_curl (pos 2); no catalog → prettified keys
    expect(text.indexOf('Side plank')).toBeLessThan(text.indexOf('Bicep curl'))
  })

  it('uses the catalog display name, falls back to a prettified key', () => {
    const w = mount(WorkoutTemplateCard, { props: { template, exercises } })
    expect(w.text()).toContain('Bicep curls') // from catalog
    expect(w.text()).toContain('Side plank') // prettified from side_plank
    expect(w.text()).not.toContain('side_plank')
  })

  it('shows load in lb (kg → lb) and the variant chip', () => {
    const w = mount(WorkoutTemplateCard, { props: { template } })
    expect(w.text()).toContain('10 lb') // 4.54 kg → 10 lb
    expect(w.text()).toContain('left') // variant chip
  })

  it('formats durations (480s → 8 min, 60s → 1 min)', () => {
    const w = mount(WorkoutTemplateCard, { props: { template } })
    expect(w.text()).toContain('8 min') // easy_jog 480s
    expect(w.text()).toContain('1 min') // side_plank / bicep 60s
  })

  it('emits edit and delete from the header actions', async () => {
    const w = mount(WorkoutTemplateCard, { props: { template } })
    await w.find('button[aria-label="Edit workout"]').trigger('click')
    await w.find('button[aria-label="Delete workout"]').trigger('click')
    expect(w.emitted('edit')).toHaveLength(1)
    expect(w.emitted('delete')).toHaveLength(1)
  })

  it('hides the coach action buttons in readonly mode (SB-332)', () => {
    const w = mount(WorkoutTemplateCard, { props: { template, readonly: true } })
    expect(w.find('button[aria-label="Edit workout"]').exists()).toBe(false)
    expect(w.find('button[aria-label="Delete workout"]').exists()).toBe(false)
    // content still renders
    expect(w.text()).toContain('Monday - Circuit')
  })

  it('shows the created date when present (SB-333)', () => {
    const w = mount(WorkoutTemplateCard, {
      props: { template: { ...template, created_at: '2026-07-20T12:00:00Z' } },
    })
    expect(w.text()).toContain('Added')
  })

  it('shows a completed badge with the last session date (SB-334)', () => {
    const w = mount(WorkoutTemplateCard, {
      props: { template: { ...template, has_session: true, last_session_date: '2026-07-23' } },
    })
    expect(w.text()).toContain('Completed')
    expect(w.text()).toContain('Jul 23')
    expect(w.text()).not.toContain('Not logged')
  })

  it('shows "Not logged" when no session exists (SB-334)', () => {
    const w = mount(WorkoutTemplateCard, {
      props: { template: { ...template, has_session: false } },
    })
    expect(w.text()).toContain('Not logged')
  })

  it('shows the scheduled date when set (SB-335)', () => {
    const w = mount(WorkoutTemplateCard, {
      props: { template: { ...template, scheduled_for: '2026-07-28' } },
    })
    expect(w.text()).toContain('Jul 28')
  })
})

// --- SB-484: the card had been under-reporting the plan ----------------------

const sbTemplate = (items: TemplateItem[]): WorkoutTemplate => ({
  ...template,
  id: 't2',
  name: 'Speed Endurance — Track',
  items,
})

const render484 = (items: TemplateItem[]) =>
  mount(WorkoutTemplateCard, { props: { template: sbTemplate(items), readonly: true } })

describe('WorkoutTemplateCard — full prescription (SB-484)', () => {
  it('shows items in sections outside warmup/main/cooldown', () => {
    // The worst of the bug, because it was silent: `sections` filtered against
    // a fixed whitelist while `section` is free text, so a speed_endurance
    // block rendered without its intervals and nothing said anything was gone.
    const w = render484([
      ti({ id: 'a', position: 0, section: 'warmup', exercise_key: 'easy_jog' }),
      ti({ id: 'b', position: 1, section: 'speed_endurance', exercise_key: 'interval_run' }),
      ti({ id: 'c', position: 2, section: 'accelerations', exercise_key: 'ground_start_accel' }),
    ])

    const text = w.text()
    expect(text).toContain('Interval run')
    expect(text).toContain('Ground start accel')
    expect(text).toContain('Speed endurance')
  })

  it('renders a rep range rather than its lower bound', () => {
    const w = render484([ti({ position: 0, target_reps: 8, target_reps_max: 12 })])
    expect(w.text()).toContain('8-12 reps')
  })

  it('renders a heart-rate zone', () => {
    const w = render484([ti({ position: 0, target_hr_min: 120, target_hr_max: 145 })])
    expect(w.text()).toContain('HR 120-145')
  })

  it('renders alternatives as one choice', () => {
    const w = render484([
      ti({
        position: 0,
        exercise_key: 'easy_jog',
        option_group: 'aerobic',
        option_group_label: 'Aerobic engine',
      }),
      ti({ position: 1, exercise_key: 'bike', option_group: 'aerobic' }),
      ti({ position: 2, exercise_key: 'jump_rope', option_group: 'aerobic' }),
    ])
    const text = w.text()
    expect(text).toContain('Aerobic engine')
    expect(text).toContain('do one')
  })

  it('shows full recovery instead of nothing', () => {
    const w = render484([ti({ position: 0, rest_mode: 'full' })])
    expect(w.text()).toContain('full recovery')
  })

  it('shows a load range in lb', () => {
    const w = render484([ti({ position: 0, target_load_kg: 2.26796, target_load_max_kg: 3.62874 })])
    expect(w.text()).toContain('5-8 lb')
  })

  it('renders every item of a twelve-item circuit', () => {
    const items = Array.from({ length: 12 }, (_, i) =>
      ti({ id: `i${i}`, position: i, exercise_key: `ex_${i}`, target_duration_seconds: 30 }),
    )
    expect(render484(items).findAll('li')).toHaveLength(12)
  })
})

describe('WorkoutTemplateCard — exercise descriptions (SB-525)', () => {
  // Gabe hit "Aquaman" mid-workout with no way to find out what it was, while
  // its cues sat in the catalog. The card now reveals them in place.
  const aquaman = {
    key: 'aquaman',
    display_name: 'Aquaman',
    measures: [],
    cues: ['Prone: lift opposite arm + leg', 'Long through the spine'],
    instructions: null,
  } as unknown as Exercise

  const withAquaman = {
    ...template,
    items: [ti({ id: 'a1', exercise_key: 'aquaman', position: 0, target_duration_seconds: 60 })],
  }

  const render = () =>
    mount(WorkoutTemplateCard, {
      props: { template: withAquaman, exercises: [aquaman] },
    })

  it('hides the description until asked — the list stays scannable', () => {
    const w = render()
    expect(w.text()).toContain('Aquaman')
    expect(w.find('[data-testid="exercise-description"]').exists()).toBe(false)
  })

  it('reveals the cues when the exercise name is tapped', async () => {
    const w = render()
    await w.get('[data-testid="describe-aquaman"]').trigger('click')
    const panel = w.get('[data-testid="exercise-description"]')
    expect(panel.text()).toContain('Prone: lift opposite arm + leg')
    expect(panel.text()).toContain('Long through the spine')
  })

  it('closes again on a second tap', async () => {
    const w = render()
    const trigger = w.get('[data-testid="describe-aquaman"]')
    await trigger.trigger('click')
    await trigger.trigger('click')
    expect(w.find('[data-testid="exercise-description"]').exists()).toBe(false)
  })

  it('exposes the open state to screen readers', async () => {
    const w = render()
    const trigger = w.get('[data-testid="describe-aquaman"]')
    expect(trigger.attributes('aria-expanded')).toBe('false')
    await trigger.trigger('click')
    expect(trigger.attributes('aria-expanded')).toBe('true')
  })

  it('opens each item independently, so L and R can be compared', async () => {
    // Closing one to read the other is friction mid-workout.
    const w = mount(WorkoutTemplateCard, {
      props: {
        template: {
          ...template,
          items: [
            ti({ id: 'l', exercise_key: 'side_plank', position: 0, variant: 'left' }),
            ti({ id: 'r', exercise_key: 'side_plank', position: 1, variant: 'right' }),
          ],
        },
        exercises: [{ key: 'side_plank', display_name: 'Side plank', measures: [], cues: ['Stack the hips'], instructions: null } as unknown as Exercise],
      },
    })
    const triggers = w.findAll('[data-testid="describe-side_plank"]')
    expect(triggers).toHaveLength(2)
    await triggers[0].trigger('click')
    await triggers[1].trigger('click')
    expect(w.findAll('[data-testid="exercise-description"]')).toHaveLength(2)
  })

  it('is honest when an exercise has no description yet', async () => {
    const w = mount(WorkoutTemplateCard, {
      props: {
        template: withAquaman,
        exercises: [{ ...aquaman, cues: [], instructions: null } as unknown as Exercise],
      },
    })
    await w.get('[data-testid="describe-aquaman"]').trigger('click')
    expect(w.get('[data-testid="exercise-description"]').text()).toContain('No description added')
  })
})
