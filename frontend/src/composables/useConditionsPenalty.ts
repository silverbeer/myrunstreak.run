import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { ConditionsPenalty } from '@/types/runs'

/** The user's hot+humid pace penalty from history (SB-304). Best-effort — a
 * failure just leaves the steamy flag showing its generic message. */
export function useConditionsPenalty() {
  const penalty = ref<ConditionsPenalty | null>(null)

  const load = async (): Promise<void> => {
    try {
      penalty.value = await apiCall<ConditionsPenalty>('/runs/conditions-penalty')
    } catch {
      penalty.value = null
    }
  }

  return { penalty, load }
}
