/**
 * Which athlete a workout view is acting on (SB-486).
 *
 * The builder, logger and print views are already athlete-scoped — they were
 * just only reachable at `/coach/:athleteId/...`, so the athlete came from the
 * route. An athlete working on their own workouts has no such param: they are
 * the subject.
 *
 * Both cases resolve to an athlete id, which is all the views and the existing
 * `actAs()` header need. The API authorises either caller identically —
 * `can_access_athlete` returns true for the coach *and* for the linked athlete
 * (backend/admin.py) — so nothing else has to branch on who is asking.
 */
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useMyAthlete } from '@/composables/useCoach'

export function useActingAthlete() {
  const route = useRoute()
  const { myAthlete, loadMyAthlete } = useMyAthlete()
  const resolved = ref(false)

  /** True when the caller is working on their own workouts, not an athlete's. */
  const isSelf = computed(() => !route.params.athleteId)

  const athleteId = computed<string | null>(() => {
    const param = route.params.athleteId as string | undefined
    return param ?? myAthlete.value?.id ?? null
  })

  /** Where this view's back-link and post-save redirect should go. */
  const homePath = computed(() =>
    isSelf.value ? '/my/workouts' : `/coach/${route.params.athleteId as string}`,
  )

  /**
   * Resolve the athlete. Only fetches `/me/athlete` when there is no route
   * param, so the coach path costs nothing extra.
   */
  async function resolveAthlete(): Promise<string | null> {
    if (!route.params.athleteId) await loadMyAthlete()
    resolved.value = true
    return athleteId.value
  }

  return { athleteId, isSelf, homePath, resolved, resolveAthlete }
}
