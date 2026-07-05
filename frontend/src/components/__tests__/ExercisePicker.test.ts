import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ExercisePicker from '../ExercisePicker.vue'
import type { Exercise, MovementPattern } from '@/types/workout'

const make = (over: Partial<Exercise>): Exercise => ({
  key: 'k',
  display_name: 'X',
  category: 'strength',
  measures: [],
  is_benchmark: false,
  owner_id: null,
  visibility: 'public',
  created_by: null,
  forked_from: null,
  aliases: [],
  movement_pattern: null,
  equipment: [],
  body_region: [],
  laterality: null,
  difficulty: null,
  tags: [],
  media_url: null,
  thumbnail_url: null,
  cues: [],
  instructions: null,
  ...over,
})

const catalog: Exercise[] = [
  make({ key: 'pushups', display_name: 'Push-ups', movement_pattern: 'push', aliases: ['press-up'] }),
  make({ key: 'plank', display_name: 'Plank', movement_pattern: 'isometric' }),
  make({
    key: 'goblet_squat',
    display_name: 'Goblet Squat',
    movement_pattern: 'squat',
    visibility: 'private',
    owner_id: 'u1',
    aliases: ['kb squat'],
  }),
]

const byText = (w: ReturnType<typeof mount>, text: string) =>
  w.findAll('button').find((b) => b.text() === text)!

const setSearch = (w: ReturnType<typeof mount>, v: string) =>
  w.find('[data-testid="exercise-search"]').setValue(v)

describe('ExercisePicker', () => {
  it('renders all exercises by default', () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog } })
    expect(w.find('[data-testid="ex-pushups"]').exists()).toBe(true)
    expect(w.find('[data-testid="ex-plank"]').exists()).toBe(true)
    expect(w.find('[data-testid="ex-goblet_squat"]').exists()).toBe(true)
  })

  it('search filters by display name', async () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog } })
    await setSearch(w, 'goblet')
    expect(w.find('[data-testid="ex-goblet_squat"]').exists()).toBe(true)
    expect(w.find('[data-testid="ex-pushups"]').exists()).toBe(false)
  })

  it('search matches aliases', async () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog } })
    await setSearch(w, 'press-up')
    expect(w.find('[data-testid="ex-pushups"]').exists()).toBe(true)
    expect(w.find('[data-testid="ex-goblet_squat"]').exists()).toBe(false)
  })

  it('ownership facet Mine shows only owned exercises', async () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog } })
    await byText(w, 'Mine').trigger('click')
    expect(w.find('[data-testid="ex-goblet_squat"]').exists()).toBe(true)
    expect(w.find('[data-testid="ex-pushups"]').exists()).toBe(false)
  })

  it('ownership facet Public excludes private exercises', async () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog } })
    await byText(w, 'Public').trigger('click')
    expect(w.find('[data-testid="ex-goblet_squat"]').exists()).toBe(false)
    expect(w.find('[data-testid="ex-pushups"]').exists()).toBe(true)
  })

  it('pattern facet filters to that movement', async () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog } })
    await byText(w, 'push').trigger('click')
    expect(w.find('[data-testid="ex-pushups"]').exists()).toBe(true)
    expect(w.find('[data-testid="ex-plank"]').exists()).toBe(false)
  })

  it('shows a balance nudge when the selection is imbalanced', () => {
    const w = mount(ExercisePicker, {
      props: { exercises: catalog, selectedKeys: ['pushups'] }, // push, no pull
    })
    const nudge = w.find('[data-testid="balance-nudge"]')
    expect(nudge.exists()).toBe(true)
    expect(nudge.text()).toMatch(/pull/i)
  })

  it('no nudge without a selection', () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog } })
    expect(w.find('[data-testid="balance-nudge"]').exists()).toBe(false)
  })

  it("does not render 'none' as an equipment tag", () => {
    const ex = [make({ key: 'sprint_x', display_name: 'Sprint X', equipment: ['none'] })]
    const w = mount(ExercisePicker, { props: { exercises: ex } })
    expect(w.find('[data-testid="ex-sprint_x"]').text()).not.toContain('none')
  })

  it('renders real equipment tags', () => {
    const ex = [make({ key: 'carry_x', display_name: 'Carry X', equipment: ['dumbbell', 'none'] })]
    const w = mount(ExercisePicker, { props: { exercises: ex } })
    const card = w.find('[data-testid="ex-carry_x"]').text()
    expect(card).toContain('dumbbell')
    expect(card).not.toContain('none')
  })

  it('clicking a card emits toggle in select mode', async () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog, mode: 'select' } })
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    expect(w.emitted('toggle')?.[0]?.[0]).toMatchObject({ key: 'pushups' })
  })

  it('manage mode shows Publish on own private exercises and emits publish', async () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog, mode: 'manage' } })
    const pub = w.find('[data-testid="publish-goblet_squat"]')
    expect(pub.exists()).toBe(true)
    // public exercise has no publish button
    expect(w.find('[data-testid="publish-pushups"]').exists()).toBe(false)
    await pub.trigger('click')
    expect(w.emitted('publish')?.[0]).toEqual(['goblet_squat'])
  })

  it('select mode has no publish buttons', () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog, mode: 'select' } })
    expect(w.find('[data-testid="publish-goblet_squat"]').exists()).toBe(false)
  })

  it('empty search offers create; submitting emits a private create payload prefilled from the query', async () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog } })
    await setSearch(w, 'zzz new move')
    expect(w.find('[data-testid="empty"]').exists()).toBe(true)
    await w.find('[data-testid="empty"] button').trigger('click')
    expect(w.find('[data-testid="create-form"]').exists()).toBe(true)
    expect((w.find('[data-testid="create-name"]').element as HTMLInputElement).value).toBe('zzz new move')
    await w.find('[data-testid="create-submit"]').trigger('submit')
    const payload = w.emitted('create')?.[0]?.[0] as Record<string, unknown>
    expect(payload).toMatchObject({ display_name: 'zzz new move', visibility: 'private' })
  })

  it('create with the public checkbox emits a public payload', async () => {
    const w = mount(ExercisePicker, { props: { exercises: catalog } })
    await setSearch(w, 'brand new')
    await w.find('[data-testid="empty"] button').trigger('click')
    await w.find('[data-testid="create-public"]').setValue(true)
    await w.find('[data-testid="create-submit"]').trigger('submit')
    const payload = w.emitted('create')?.[0]?.[0] as Record<string, unknown>
    expect(payload).toMatchObject({ visibility: 'public' })
  })
})
