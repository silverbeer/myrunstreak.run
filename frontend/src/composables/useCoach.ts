import { computed, ref } from 'vue'
import { apiCall } from '@/config/api'
import type {
  Athlete,
  AthleteCreate,
  AthleteProfileUpdate,
  MyRoles,
  WorkoutSession,
} from '@/types/coach'

// Roles are shared app-wide (the nav gates the Coach link on them), so cache
// them in module scope — one fetch feeds AppHeader and every coach view.
const roles = ref<MyRoles | null>(null)
const rolesLoaded = ref(false)

const isCoach = computed(
  () => !!roles.value && (roles.value.roles.includes('coach') || roles.value.is_admin),
)

async function loadRoles(force = false): Promise<void> {
  if (rolesLoaded.value && !force) return
  try {
    roles.value = await apiCall<MyRoles>('/me/roles')
  } catch {
    roles.value = { roles: [], is_admin: false }
  } finally {
    rolesLoaded.value = true
  }
}

/** Header that makes an authenticated call act on an athlete's behalf. */
const actAs = (athleteId: string) => ({ 'X-Act-As-Athlete': athleteId })

// The athlete the logged-in user IS (via linked_user_id), or null. Shared
// app-wide so the nav can gate a "My Profile" link on it.
const myAthlete = ref<Athlete | null>(null)
const myAthleteLoaded = ref(false)

async function loadMyAthlete(force = false): Promise<void> {
  if (myAthleteLoaded.value && !force) return
  try {
    myAthlete.value = await apiCall<Athlete | null>('/me/athlete')
  } catch {
    myAthlete.value = null
  } finally {
    myAthleteLoaded.value = true
  }
}

/** PATCH an athlete's profile. Server enforces field-level permissions. */
export async function updateAthleteProfile(
  athleteId: string,
  patch: AthleteProfileUpdate,
): Promise<Athlete> {
  return apiCall<Athlete>(`/athletes/${athleteId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export function useMyAthlete() {
  return { myAthlete, loadMyAthlete }
}

/** Invite a person to onboard as this athlete (linked on redeem). Returns the
 *  invite incl. token; the caller builds the /signup?invite=<token> link. */
export async function inviteAthlete(email: string, athleteId: string): Promise<{ token: string }> {
  return apiCall<{ token: string }>('/invites', {
    method: 'POST',
    body: JSON.stringify({ email, athlete_id: athleteId }),
  })
}

/** Add an existing user (by email) as a coach of the athlete. 404 if the email
 *  isn't a user yet (invite them as a coach first). */
export async function addCoachByEmail(athleteId: string, email: string): Promise<void> {
  await apiCall(`/athletes/${athleteId}/coaches`, {
    method: 'POST',
    body: JSON.stringify({ coach_email: email }),
  })
}

export function useCoach() {
  const athletes = ref<Athlete[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const loadAthletes = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      athletes.value = await apiCall<Athlete[]>('/athletes')
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load athletes'
    } finally {
      loading.value = false
    }
  }

  const createAthlete = async (body: AthleteCreate): Promise<Athlete | null> => {
    error.value = null
    try {
      const created = await apiCall<Athlete>('/athletes', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      athletes.value = [...athletes.value, created]
      return created
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create athlete'
      return null
    }
  }

  return { athletes, loading, error, loadAthletes, createAthlete }
}

/** State for a single athlete's detail view — profile + their sessions (act-as). */
export function useAthleteDetail(athleteId: string) {
  const athlete = ref<Athlete | null>(null)
  const sessions = ref<WorkoutSession[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      const [a, s] = await Promise.all([
        apiCall<Athlete>(`/athletes/${athleteId}`),
        apiCall<WorkoutSession[]>('/workouts/sessions?limit=50', {
          headers: actAs(athleteId),
        }),
      ])
      athlete.value = a
      sessions.value = s
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load athlete'
    } finally {
      loading.value = false
    }
  }

  return { athlete, sessions, loading, error, load }
}

export function useRoles() {
  return { roles, isCoach, loadRoles }
}
