import { apiCall } from '@/config/api'
import type { OverallStats } from '@/types/runs'
import { useRoles } from './useCoach'

// Cached for the session: the landing decision is made once (login / first
// navigation), not on every route change. Reset on logout.
let resolved: string | null = null

/**
 * Where a just-authenticated user should land (SB-265).
 *
 * Coaches (or admins) with no run history land on Coach — the runner
 * dashboard's "Connect SmashRun" CTA is a dead end for them. Anyone with runs,
 * or without the coach role, keeps the runner dashboard. Explicit user
 * preference will take precedence over this heuristic when SB-267 lands.
 *
 * Returns a route path ('/coach' | '/dashboard').
 */
export async function resolveLanding(): Promise<string> {
  if (resolved) return resolved
  const { roles, loadRoles } = useRoles()
  await loadRoles()
  const coachish = !!roles.value && (roles.value.roles.includes('coach') || roles.value.is_admin)
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

/** Forget the cached decision (logout, tests). */
export function resetLanding(): void {
  resolved = null
}
