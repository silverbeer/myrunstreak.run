import { ref, watch } from 'vue'
import { supabase } from '@/config/supabase'
import type { Unit } from '@/types/runs'

const STORAGE_KEY = 'mrs.unit'
const DEFAULT_UNIT: Unit = 'mi'

const unit = ref<Unit>(loadInitialUnit())
const loaded = ref(false)

function loadInitialUnit(): Unit {
  if (typeof window === 'undefined') return DEFAULT_UNIT
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return stored === 'mi' || stored === 'km' ? stored : DEFAULT_UNIT
}

function persistLocally(value: Unit): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, value)
  }
}

async function syncFromSupabase(): Promise<void> {
  const { data } = await supabase.auth.getUser()
  const remote = data.user?.user_metadata?.unit as Unit | undefined
  if (remote === 'mi' || remote === 'km') {
    unit.value = remote
    persistLocally(remote)
  }
  loaded.value = true
}

async function setUnit(value: Unit): Promise<void> {
  unit.value = value
  persistLocally(value)
  await supabase.auth.updateUser({ data: { unit: value } })
}

export function useUserPreferences() {
  if (!loaded.value) {
    void syncFromSupabase()
  }
  return { unit, setUnit, loaded }
}

if (typeof window !== 'undefined') {
  watch(unit, persistLocally)
}
