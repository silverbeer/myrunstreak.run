import type {
  BuilderItem,
  TemplateItemInput,
  WorkoutSectionKey,
  WorkoutTemplateInput,
  WorkoutType,
} from '@/types/workout'

export const LB_TO_KG = 0.453592

export const SECTIONS: { key: WorkoutSectionKey; label: string }[] = [
  { key: 'warmup', label: 'Warm-up' },
  { key: 'main', label: 'Main' },
  { key: 'cooldown', label: 'Cool-down' },
]

const SECTION_ORDER: WorkoutSectionKey[] = ['warmup', 'main', 'cooldown']

/** Weight the coach entered in lb → canonical kg (1 decimal), or null. */
export function lbToKg(lb: number | null): number | null {
  return lb == null ? null : Math.round(lb * LB_TO_KG * 10) / 10
}

/** Canonical kg → lb for display (whole lb), or null. */
export function kgToLb(kg: number | null | undefined): number | null {
  return kg == null ? null : Math.round(kg / LB_TO_KG)
}

/** slug key → readable fallback name ("bear_crawl" → "Bear crawl"). */
export function prettifyKey(key: string): string {
  const s = key.replace(/_/g, ' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

/**
 * Turn the builder's local items into the API payload:
 * ordered by section (warm-up → main → cool-down) then within-section order,
 * with a running `position`, and loads converted lb → kg. Pure + deterministic.
 */
export function buildTemplatePayload(
  name: string,
  type: WorkoutType,
  rounds: number,
  items: BuilderItem[],
): WorkoutTemplateInput {
  const ordered = SECTION_ORDER.flatMap((section) =>
    items.filter((it) => it.section === section),
  )
  const apiItems: TemplateItemInput[] = ordered.map((it, position) => ({
    exercise_key: it.exercise.key,
    section: it.section,
    position,
    target_reps: it.reps,
    target_duration_seconds: it.duration_s,
    target_load_kg: lbToKg(it.load_lb),
    target_distance_m: it.distance_m,
    rest_seconds: it.rest_s,
    variant: it.variant?.trim() || null,
    notes: it.notes?.trim() || null,
  }))
  return { name: name.trim(), type, rounds, items: apiItems }
}
