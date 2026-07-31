/**
 * How a prescribed target reads (SB-484).
 *
 * The CLI card, the printable sheet and the athlete's in-app card each format
 * the same fields, and they had drifted: the sheet learned ranges, heart-rate
 * zones and rest modes in SB-446/447, the athlete's card did not — so Gabe's
 * app showed "8 reps" for a prescribed 8-12 and no heart-rate zone at all.
 * One implementation, so a future dimension lands everywhere at once.
 */
import type { TemplateItem } from '@/types/workout'
import { fmtDuration, kgToLb } from '@/utils/workoutPayload'

/** A target that may be a range: (8, 12) → "8-12"; (8, null) → "8". */
export function fmtRange(
  lo?: number | null,
  hi?: number | null,
  unit = '',
): string {
  if (lo != null && hi != null && hi !== lo) return `${lo}-${hi}${unit}`
  const value = lo ?? hi
  return value != null ? `${value}${unit}` : ''
}

/** A prescribed heart-rate zone: "HR 160-175", "HR 120+", "HR ≤145". */
export function hrZoneText(item: TemplateItem): string {
  const { target_hr_min: lo, target_hr_max: hi } = item
  if (lo == null && hi == null) return ''
  if (lo != null && hi != null) return hi === lo ? `HR ${lo}` : `HR ${lo}-${hi}`
  return lo != null ? `HR ${lo}+` : `HR ≤${hi}`
}

/**
 * Rest as prescribed — which is not always a number.
 *
 * "Full recovery" and "go off how you feel" are conditions the athlete
 * resolves; showing an invented duration would misreport the plan.
 */
export function restText(item: TemplateItem): string {
  if (item.rest_mode === 'full') return 'full recovery'
  if (item.rest_seconds == null && item.rest_seconds_max == null) {
    return item.rest_mode === 'autoregulated' ? 'rest by feel' : ''
  }
  const lo = item.rest_seconds
  const hi = item.rest_seconds_max
  const range =
    lo != null && hi != null && hi !== lo
      ? `${lo}-${hi}s`
      : fmtDuration((lo ?? hi) as number)
  return item.rest_mode === 'autoregulated' ? `rest ${range} (by feel)` : `rest ${range}`
}

/** Duration, honouring a range: 40-42s rather than the lower bound alone. */
export function durationText(item: TemplateItem): string {
  const lo = item.target_duration_seconds
  const hi = item.target_duration_max_seconds
  if (lo == null && hi == null) return ''
  if (lo != null && hi != null && hi !== lo) return `${lo}-${hi}s`
  return fmtDuration((lo ?? hi) as number)
}

export interface TargetPill {
  text: string
  cls: string
}

const BASE = 'bg-gray-100 text-gray-600'
const LOAD = 'bg-amber-50 text-amber-700'
const ZONE = 'bg-rose-50 text-rose-700'
const REST = 'bg-gray-50 text-gray-400'

/** Every prescribed dimension of one item, as display pills. */
export function targetPills(item: TemplateItem): TargetPill[] {
  const out: TargetPill[] = []

  const reps = fmtRange(item.target_reps, item.target_reps_max)
  if (reps) out.push({ text: `${reps} reps`, cls: BASE })

  const duration = durationText(item)
  if (duration) out.push({ text: duration, cls: BASE })

  if (item.target_load_kg != null || item.target_load_max_kg != null) {
    // Prescribed in lb, stored canonical kg — round each bound so 5-8 lb
    // survives the round-trip instead of becoming 5-8.0000001.
    const load = fmtRange(kgToLb(item.target_load_kg), kgToLb(item.target_load_max_kg))
    if (load) out.push({ text: `${load} lb`, cls: LOAD })
  }

  if (item.target_distance_m != null) out.push({ text: `${item.target_distance_m} m`, cls: BASE })

  const zone = hrZoneText(item)
  if (zone) out.push({ text: zone, cls: ZONE })

  // Cadence carries no unit of its own: rpm on a bike, steps running, skips on
  // a rope — it follows the movement (SB-447).
  if (item.target_cadence != null) out.push({ text: `${item.target_cadence}/min`, cls: BASE })
  if (item.target_speed_kph != null)
    out.push({ text: `${Math.round(item.target_speed_kph * 0.621371)} mph`, cls: BASE })

  const rest = restText(item)
  if (rest) out.push({ text: rest, cls: REST })

  return out
}
