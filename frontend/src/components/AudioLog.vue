<template>
  <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6 mt-4">
    <div class="flex items-center gap-2 mb-1">
      <Headphones class="w-4 h-4 text-gray-700" />
      <h2 class="font-semibold text-gray-900">Audio</h2>
    </div>
    <p class="text-xs text-gray-400 mb-3">what you listened to on this run</p>

    <div class="flex flex-wrap gap-2">
      <button
        v-for="opt in OPTIONS"
        :key="opt.value"
        type="button"
        class="text-sm px-3 py-1.5 rounded-full border transition-colors inline-flex items-center gap-1.5"
        :class="selectedType === opt.value
          ? 'border-brand-500 bg-brand-50 text-brand-700 font-medium'
          : 'border-gray-200 text-gray-500 hover:border-gray-300'"
        @click="toggle(opt.value)"
      >
        <span>{{ opt.emoji }}</span> {{ opt.label }}
      </button>
    </div>

    <input
      v-model="noteDraft"
      type="text"
      maxlength="500"
      placeholder="Optional note — e.g. “Noah Kahan playlist today”"
      class="mt-3 w-full text-sm rounded-lg border border-gray-200 px-3 py-2 focus:outline-none focus:border-brand-500"
      @keyup.enter="save"
    />

    <div class="flex items-center gap-3 mt-3">
      <button
        type="button"
        class="text-sm px-4 py-1.5 rounded-lg font-medium transition-colors"
        :class="dirty && !saving
          ? 'bg-brand-600 text-white hover:bg-brand-700'
          : 'bg-gray-100 text-gray-400 cursor-not-allowed'"
        :disabled="!dirty || saving"
        @click="save"
      >
        {{ saving ? 'Saving…' : 'Save' }}
      </button>
      <span v-if="justSaved" class="text-sm text-green-600 inline-flex items-center gap-1">
        <Check class="w-4 h-4" /> Saved
      </span>
      <span v-if="error" class="text-sm text-red-600">{{ error }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Headphones, Check } from 'lucide-vue-next'
import { apiCall } from '@/config/api'
import type { AudioType } from '@/types/runs'

const props = defineProps<{
  activityId: string
  audioType: AudioType | null
  audioNote: string | null
}>()

const OPTIONS: { value: AudioType; label: string; emoji: string }[] = [
  { value: 'podcast', label: 'Podcast', emoji: '🎙️' },
  { value: 'music', label: 'Music', emoji: '🎵' },
  { value: 'audiobook', label: 'Audiobook', emoji: '📖' },
  { value: 'other', label: 'Other', emoji: '🔊' },
  { value: 'none', label: 'None', emoji: '🤫' },
]

// Saved state (what's on the server) vs the working draft.
const savedType = ref<AudioType | null>(props.audioType)
const savedNote = ref<string>(props.audioNote ?? '')
const selectedType = ref<AudioType | null>(props.audioType)
const noteDraft = ref<string>(props.audioNote ?? '')

const saving = ref(false)
const justSaved = ref(false)
const error = ref<string | null>(null)

const dirty = computed(
  () => selectedType.value !== savedType.value || noteDraft.value !== savedNote.value,
)

// Clicking the active chip clears it back to unset.
function toggle(v: AudioType): void {
  selectedType.value = selectedType.value === v ? null : v
  justSaved.value = false
}

async function save(): Promise<void> {
  if (!dirty.value || saving.value) return
  saving.value = true
  error.value = null
  try {
    const note = noteDraft.value.trim()
    await apiCall(`/runs/${encodeURIComponent(props.activityId)}/audio`, {
      method: 'PATCH',
      body: JSON.stringify({ audio_type: selectedType.value, audio_note: note || null }),
    })
    savedType.value = selectedType.value
    savedNote.value = note
    noteDraft.value = note
    justSaved.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Could not save'
  } finally {
    saving.value = false
  }
}
</script>
