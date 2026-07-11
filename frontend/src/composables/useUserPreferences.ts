import { ref, watch } from 'vue'
import { supabase } from '@/config/supabase'
import type { Unit } from '@/types/runs'

const STORAGE_KEY = 'mrs.unit'
const DEFAULT_UNIT: Unit = 'mi'

/** Where the app opens by default. 'auto' = role heuristic (SB-265/267). */
export type DefaultView = 'auto' | 'dashboard' | 'runs' | 'coach'
const VIEW_STORAGE_KEY = 'mrs.defaultView'
const DEFAULT_VIEW: DefaultView = 'auto'
const VIEW_VALUES: readonly DefaultView[] = ['auto', 'dashboard', 'runs', 'coach']

const unit = ref<Unit>(loadInitialUnit())
const defaultView = ref<DefaultView>(loadInitialView())
const loaded = ref(false)

function loadInitialUnit(): Unit {
  if (typeof window === 'undefined') return DEFAULT_UNIT
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return stored === 'mi' || stored === 'km' ? stored : DEFAULT_UNIT
}

function loadInitialView(): DefaultView {
  if (typeof window === 'undefined') return DEFAULT_VIEW
  const stored = window.localStorage.getItem(VIEW_STORAGE_KEY)
  return VIEW_VALUES.includes(stored as DefaultView) ? (stored as DefaultView) : DEFAULT_VIEW
}

function persistLocally(value: Unit): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, value)
  }
}

function persistViewLocally(value: DefaultView): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(VIEW_STORAGE_KEY, value)
  }
}

async function syncFromSupabase(): Promise<void> {
  const { data } = await supabase.auth.getUser()
  const remote = data.user?.user_metadata?.unit as Unit | undefined
  if (remote === 'mi' || remote === 'km') {
    unit.value = remote
    persistLocally(remote)
  }
  const remoteView = data.user?.user_metadata?.default_view as DefaultView | undefined
  if (remoteView && VIEW_VALUES.includes(remoteView)) {
    defaultView.value = remoteView
    persistViewLocally(remoteView)
  }
  loaded.value = true
}

async function setUnit(value: Unit): Promise<void> {
  unit.value = value
  persistLocally(value)
  await supabase.auth.updateUser({ data: { unit: value } })
}

async function setDefaultView(value: DefaultView): Promise<void> {
  defaultView.value = value
  persistViewLocally(value)
  await supabase.auth.updateUser({ data: { default_view: value } })
}

export function useUserPreferences() {
  if (!loaded.value) {
    void syncFromSupabase()
  }
  return { unit, setUnit, defaultView, setDefaultView, loaded }
}

if (typeof window !== 'undefined') {
  watch(unit, persistLocally)
  watch(defaultView, persistViewLocally)
}
