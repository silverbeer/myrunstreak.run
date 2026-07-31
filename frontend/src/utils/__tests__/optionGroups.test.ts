import { describe, it, expect } from 'vitest'
import { groupOptionItems } from '../optionGroups'
import type { TemplateItem } from '@/types/workout'

const item = (over: Partial<TemplateItem> & { id: string; position: number }): TemplateItem => ({
  exercise_key: 'plank',
  section: 'main',
  target_reps: null,
  target_duration_seconds: null,
  target_load_kg: null,
  target_distance_m: null,
  rest_seconds: null,
  variant: null,
  notes: null,
  ...over,
})

describe('groupOptionItems', () => {
  it('leaves mandatory items alone', () => {
    const rows = groupOptionItems([
      item({ id: 'a', position: 0, exercise_key: 'pushups' }),
      item({ id: 'b', position: 1, exercise_key: 'plank' }),
    ])
    expect(rows.map((r) => r.kind)).toEqual(['item', 'item'])
  })

  it('folds the aerobic day into one pick-one block', () => {
    // Matthew's actual prescription: run OR bike OR jump rope.
    const rows = groupOptionItems([
      item({ id: 'w', position: 0, exercise_key: 'dynamic_drills' }),
      item({
        id: 'r',
        position: 1,
        exercise_key: 'easy_jog',
        option_group: 'aerobic',
        option_group_label: 'Aerobic engine',
      }),
      item({ id: 'b', position: 2, exercise_key: 'bike', option_group: 'aerobic' }),
      item({ id: 'j', position: 3, exercise_key: 'jump_rope', option_group: 'aerobic' }),
      item({ id: 'p', position: 4, exercise_key: 'plank' }),
    ])

    expect(rows.map((r) => r.kind)).toEqual(['item', 'group', 'item'])
    const group = rows[1]
    if (group.kind !== 'group') throw new Error('expected a group')
    expect(group.label).toBe('Aerobic engine')
    expect(group.items.map((i) => i.exercise_key)).toEqual(['easy_jog', 'bike', 'jump_rope'])
  })

  it('places the group where its first member sits, not at the end', () => {
    const rows = groupOptionItems([
      item({ id: 'a', position: 0, exercise_key: 'bike', option_group: 'aerobic' }),
      item({ id: 'b', position: 1, exercise_key: 'plank' }),
    ])
    expect(rows[0].kind).toBe('group')
  })

  it('keeps non-contiguous alternatives in one block', () => {
    // A coach editing a plan can leave the options separated; repeating the
    // heading would read as two separate choices.
    const rows = groupOptionItems([
      item({ id: 'a', position: 0, exercise_key: 'easy_jog', option_group: 'aerobic' }),
      item({ id: 'b', position: 1, exercise_key: 'plank' }),
      item({ id: 'c', position: 2, exercise_key: 'bike', option_group: 'aerobic' }),
    ])

    expect(rows.map((r) => r.kind)).toEqual(['group', 'item'])
    const group = rows[0]
    if (group.kind !== 'group') throw new Error('expected a group')
    expect(group.items).toHaveLength(2)
  })

  it('falls back to a generic label when the coach did not write one', () => {
    const rows = groupOptionItems([
      item({ id: 'a', position: 0, exercise_key: 'bike', option_group: 'aerobic' }),
    ])
    const group = rows[0]
    if (group.kind !== 'group') throw new Error('expected a group')
    expect(group.label).toBe('Pick one')
  })

  it('sorts by position regardless of input order', () => {
    const rows = groupOptionItems([
      item({ id: 'b', position: 2, exercise_key: 'plank' }),
      item({ id: 'a', position: 1, exercise_key: 'pushups' }),
    ])
    expect(rows.map((r) => (r.kind === 'item' ? r.item.exercise_key : ''))).toEqual([
      'pushups',
      'plank',
    ])
  })

  it('treats distinct groups separately', () => {
    const rows = groupOptionItems([
      item({ id: 'a', position: 0, exercise_key: 'easy_jog', option_group: 'aerobic' }),
      item({ id: 'b', position: 1, exercise_key: 'pull_up', option_group: 'upper' }),
    ])
    expect(rows.map((r) => r.kind)).toEqual(['group', 'group'])
  })
})
