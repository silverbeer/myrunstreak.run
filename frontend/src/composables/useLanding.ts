import { apiCall } from '@/config/api'
import { supabase } from '@/config/supabase'
import type { OverallStats } from '@/types/runs'
import { useRoles } from './useCoach'

// Cached for the session: the landing decision is made once (login / first
// navigation), not on every route change. Reset on logout.
let resolved: string | null = null

const PREFERENCE_PATHS: Record<string, string> = {
  dashboard: '/dashboard',
  runs: '/runs',
  coach: '/coach',
}

/**
 * Where a just-authenticated user should land (SB-265 / SB-267).
 *
 * Precedence: an explicit "default view" preference (Settings, stored in
 * Supabase user_metadata) → role heuristic → runner dashboard. The heuristic:
 * coaches (or admins) with no run history land on Coach — the runner
 * dashboard's "Connect SmashRun" CTA is a dead end for them.
 *
 * Returns a route path ('/coach' | '/runs' | '/dashboard').
 */
export async function resolveLanding(): Promise<string> {
  if (resolved) return resolved

  // Roles gate both the preference and the heuristic below. loadRoles() is
  // module-cached and swallows its own errors (defaults to no roles).
  const { roles, loadRoles } = useRoles()
  await loadRoles()
  const coachish = !!roles.value && (roles.value.roles.includes('coach') || roles.value.is_admin)

  // 1. Explicit preference wins (SB-267). 'auto' or absent falls through. A
  //    'coach' preference is honored ONLY for coaches/admins — otherwise a stale
  //    preference dead-ends a non-coach on /coach ("Coach privileges required"),
  //    so it falls through to the heuristic instead (SB-331).
  try {
    const { data } = await supabase.auth.getUser()
    const pref = data.user?.user_metadata?.default_view as string | undefined
    if (pref && PREFERENCE_PATHS[pref] && (pref !== 'coach' || coachish)) {
      resolved = PREFERENCE_PATHS[pref]
      return resolved
    }
  } catch {
    // fall through to the heuristic
  }

  // 2. Role heuristic (SB-265).
  if (!coachish) {
    resolved = '/dashboard'
    return resolved
  }
  try {
    const stats = await apiCall<OverallStats>('/stats/overall')
    resolved = stats.total_runs === 0 ? '/coach' : '/dashboard'
  } catch {
    resolved = '/dashboard'
  }
  return resolved
}

/** Forget the cached decision (logout, or the preference just changed). */
export function resetLanding(): void {
  resolved = null
}
