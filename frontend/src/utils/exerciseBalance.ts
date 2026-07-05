import type { Exercise, MovementPattern } from '@/types/workout'

/**
 * Balance nudges — the "programming assistant" heart of the exercise picker.
 *
 * Given the exercises already chosen for a workout, flag obvious movement-pattern
 * imbalances so the coach builds a balanced session. Pure + deterministic so it's
 * trivially testable and reusable (component + any future analysis).
 */

/** Count selected exercises per movement pattern (nulls ignored). */
export function patternCounts(exercises: Exercise[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const ex of exercises) {
    const p = ex.movement_pattern
    if (p) counts[p] = (counts[p] ?? 0) + 1
  }
  return counts
}

// Complementary pairs: if you program the first with none of the second, nudge.
const PAIRS: ReadonlyArray<readonly [MovementPattern, MovementPattern, string]> = [
  ['push', 'pull', 'You have push but no pull — add a pull to balance the shoulders.'],
  ['squat', 'hinge', 'Squat but no hinge — add a hinge (glutes/hamstrings).'],
  ['anti_rotation', 'rotation', 'Anti-rotation but no rotation — consider a rotational movement.'],
]

/**
 * Nudges for the current selection. Empty when balanced (or too few to judge).
 * Only fires when the first pattern is present and its complement is absent.
 */
export function balanceNudges(exercises: Exercise[]): string[] {
  const counts = patternCounts(exercises)
  const nudges: string[] = []
  for (const [a, b, message] of PAIRS) {
    if ((counts[a] ?? 0) > 0 && (counts[b] ?? 0) === 0) nudges.push(message)
  }
  return nudges
}
