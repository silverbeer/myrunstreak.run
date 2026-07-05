import { describe, it, expect } from 'vitest'
import { patternCounts, balanceNudges } from '@/utils/exerciseBalance'
import type { Exercise, MovementPattern } from '@/types/workout'

const ex = (movement_pattern: MovementPattern | null, key = 'k'): Exercise => ({
  key,
  display_name: 'X',
  category: 'strength',
  measures: [],
  is_benchmark: false,
  owner_id: null,
  visibility: 'public',
  created_by: null,
  forked_from: null,
  aliases: [],
  movement_pattern,
  equipment: [],
  body_region: [],
  laterality: null,
  difficulty: null,
  tags: [],
  media_url: null,
  thumbnail_url: null,
  cues: [],
  instructions: null,
})

describe('patternCounts', () => {
  it('counts by movement pattern, ignoring nulls', () => {
    const counts = patternCounts([ex('push', 'a'), ex('push', 'b'), ex('pull', 'c'), ex(null, 'd')])
    expect(counts).toEqual({ push: 2, pull: 1 })
  })
})

describe('balanceNudges', () => {
  it('nudges push without pull', () => {
    const n = balanceNudges([ex('push')])
    expect(n).toHaveLength(1)
    expect(n[0]).toMatch(/pull/i)
  })

  it('no push/pull nudge when both present', () => {
    const n = balanceNudges([ex('push', 'a'), ex('pull', 'b')])
    expect(n.join(' ')).not.toMatch(/no pull/i)
  })

  it('nudges squat without hinge', () => {
    expect(balanceNudges([ex('squat')])[0]).toMatch(/hinge/i)
  })

  it('empty selection → no nudges', () => {
    expect(balanceNudges([])).toEqual([])
  })

  it('balanced selection → no nudges', () => {
    const n = balanceNudges([ex('push', 'a'), ex('pull', 'b'), ex('squat', 'c'), ex('hinge', 'd')])
    expect(n).toEqual([])
  })
})
