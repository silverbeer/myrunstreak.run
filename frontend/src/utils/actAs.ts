/**
 * Who a workout request is about (SB-578).
 *
 * Workout routes take an optional `X-Act-As-Athlete` header. Present, it names
 * the athlete the caller is acting for; the backend verifies they may. **Absent,
 * the request is about the caller themselves** — `acting_athlete` returns None
 * and the repositories write self-owned rows (`athlete_id` NULL), which is the
 * shape `workout_sessions` has supported since it was created.
 *
 * So a null athlete is not a missing value to guard against — it is the ordinary
 * "this is mine" case. Sending the header with an empty or "null" string would
 * be a 422; omitting it is the whole mechanism.
 */
export function actAs(athleteId: string | null | undefined): Record<string, string> {
  return athleteId ? { 'X-Act-As-Athlete': athleteId } : {}
}
