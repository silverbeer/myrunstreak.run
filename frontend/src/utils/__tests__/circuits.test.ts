import { describe, it, expect } from 'vitest'
import {
  groupByBlock,
  roundsFor,
  templateRoundsAreMeaningful,
} from '@/utils/circuits'
import type { TemplateBlock, TemplateItem } from '@/types/workout'

const item = (id: string, position: number, block_id: string | null = null): TemplateItem =>
  ({
    id,
    exercise_key: id,
    section: 'main',
    position,
    block_id,
    target_reps: null,
    target_duration_seconds: null,
    target_load_kg: null,
    target_distance_m: null,
    rest_seconds: null,
    variant: null,
    notes: null,
  }) as TemplateItem

const block = (id: string, rounds: number, rest: number | null = null): TemplateBlock => ({
  id,
  template_id: 't1',
  label: `Circuit ${id.toUpperCase()}`,
  position: 0,
  rounds,
  rest_after_seconds: rest,
})

describe('groupByBlock (SB-543)', () => {
  it('splits a section into its circuits, in order', () => {
    const groups = groupByBlock(
      [item('a', 0, 'b1'), item('b', 1, 'b1'), item('c', 2, 'b2')],
      [block('b1', 2), block('b2', 1)],
    )
    expect(groups).toHaveLength(2)
    expect(groups[0].block?.id).toBe('b1')
    expect(groups[0].items.map((i) => i.id)).toEqual(['a', 'b'])
    expect(groups[1].items.map((i) => i.id)).toEqual(['c'])
  })

  it('keeps items outside any circuit in their own group', () => {
    // The warm-up is not a circuit and must render as it always did.
    const groups = groupByBlock([item('warm', 0), item('a', 1, 'b1')], [block('b1', 2)])
    expect(groups[0].block).toBeNull()
    expect(groups[0].items.map((i) => i.id)).toEqual(['warm'])
    expect(groups[1].block?.id).toBe('b1')
  })

  it('partitions rather than buckets, so a circuit stays contiguous', () => {
    // Same block id either side of a loose item: three groups, not two. The
    // coach's order is the prescription — reordering it would be a rewrite.
    const groups = groupByBlock(
      [item('a', 0, 'b1'), item('loose', 1), item('b', 2, 'b1')],
      [block('b1', 2)],
    )
    expect(groups.map((g) => g.items.map((i) => i.id))).toEqual([['a'], ['loose'], ['b']])
  })

  it('treats an item pointing at a missing block as loose', () => {
    const groups = groupByBlock([item('a', 0, 'gone')], [])
    expect(groups[0].block).toBeNull()
  })

  it('has nothing to group when there are no items', () => {
    expect(groupByBlock([], [block('b1', 2)])).toEqual([])
  })
})

describe('roundsFor (SB-543)', () => {
  it('takes the rounds from the circuit', () => {
    const [g] = groupByBlock([item('a', 0, 'b1')], [block('b1', 2)])
    expect(roundsFor(g, 1)).toBe(2)
  })

  it('falls back to the template for a blockless group', () => {
    const [g] = groupByBlock([item('a', 0)], [])
    expect(roundsFor(g, 3)).toBe(3)
  })

  it('is one when neither says otherwise', () => {
    const [g] = groupByBlock([item('a', 0)], [])
    expect(roundsFor(g, undefined)).toBe(1)
  })
})

describe('templateRoundsAreMeaningful (SB-543)', () => {
  it('is false once rounds live on blocks', () => {
    // `workout_templates.rounds` stays 1 for a circuit template, so showing it
    // says "1 Round" on a workout done twice.
    expect(templateRoundsAreMeaningful([block('b1', 2)])).toBe(false)
  })

  it('is true for a simple template', () => {
    expect(templateRoundsAreMeaningful([])).toBe(true)
    expect(templateRoundsAreMeaningful(undefined)).toBe(true)
  })
})
