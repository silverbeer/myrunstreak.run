<template>
  <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
    <h2 class="text-lg font-semibold text-gray-900 mb-1">Import a run</h2>
    <p class="text-sm text-gray-500 mb-4">
      Upload an activity file from Strava, Garmin, Polar, Coros or SmashRun. Every platform
      lets you export your own data, so this works without connecting an account.
    </p>

    <!--
      The drop zone is a <label>: the click path is the file input's own, so the
      picker opens on mobile (where drag-and-drop doesn't exist) and via the
      keyboard, without re-implementing either.
    -->
    <label
      class="block border-2 border-dashed rounded-xl px-4 py-8 text-center cursor-pointer transition"
      :class="
        dragging
          ? 'border-brand-500 bg-brand-50'
          : 'border-gray-200 hover:border-gray-300 bg-gray-50'
      "
      @dragover.prevent="dragging = true"
      @dragenter.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="handleDrop"
    >
      <!--
        `accept` is deliberately broader than the extension list. iOS maps
        extensions to UTIs, and an unrecognised one greys the file out in the
        Files app — a .tcx export would be unselectable on the phone, which is
        where most of these imports will happen. The generic types keep the
        picker open; validation still runs on our side, then the server's.
      -->
      <input
        ref="input"
        type="file"
        class="sr-only"
        :accept="acceptAttr"
        :disabled="importing"
        @change="handlePick"
      />
      <svg
        class="w-8 h-8 mx-auto text-gray-400 mb-2"
        :class="{ 'animate-pulse': importing }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
        />
      </svg>
      <p class="text-sm font-semibold text-gray-700">
        {{ importing ? 'Importing…' : 'Choose a file' }}
      </p>
      <p class="hidden sm:block text-xs text-gray-500 mt-1">or drop one here</p>
      <p class="text-xs text-gray-400 mt-2">
        {{ formats.extensions.join(', ') }} · up to {{ limitLabel }}
      </p>
    </label>

    <!-- Rejected before upload, or refused by the server. Either way it says why. -->
    <div
      v-if="error"
      class="mt-4 rounded-lg border border-red-100 bg-red-50 px-4 py-3"
      role="alert"
    >
      <p class="text-sm text-red-700">{{ error }}</p>
      <button type="button" class="text-xs text-red-600 underline mt-1" @click="clear">
        Try another file
      </button>
    </div>

    <div
      v-else-if="result"
      class="mt-4 rounded-lg border px-4 py-3"
      :class="
        result.status === 'duplicate'
          ? 'border-amber-100 bg-amber-50'
          : 'border-green-100 bg-green-50'
      "
    >
      <!--
        A re-upload is a reasonable thing to do, so it reads as a no-op rather
        than a failure — the run it already matched is still linked.
      -->
      <p
        class="text-sm font-semibold"
        :class="result.status === 'duplicate' ? 'text-amber-800' : 'text-green-800'"
      >
        {{ result.status === 'duplicate' ? 'Already imported' : 'Run imported' }}
      </p>
      <p class="text-sm text-gray-600 mt-0.5">
        {{ formatDate(result.start_date_time_local) }} ·
        {{ formatDistanceWithUnit(result.distance_km, unit) }} ·
        {{ formatDuration(result.duration_seconds) }}
        <span v-if="!result.has_track" class="text-gray-400">· no GPS track</span>
      </p>
      <div class="flex items-center gap-3 mt-2">
        <RouterLink
          :to="{ name: 'run-detail', params: { activityId: result.activity_id } }"
          class="text-xs font-semibold text-brand-600 hover:underline"
        >
          View run
        </RouterLink>
        <button type="button" class="text-xs text-gray-500 underline" @click="clear">
          Import another
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { formatSize, useImport } from '@/composables/useImport'
import { useUserPreferences } from '@/composables/useUserPreferences'
import { formatDate, formatDistanceWithUnit, formatDuration } from '@/utils/format'

const emit = defineEmits<{
  imported: [activityId: string]
}>()

const { importFile, loadFormats, reset, importing, error, result, formats } = useImport()
const { unit } = useUserPreferences()

const input = ref<HTMLInputElement | null>(null)
const dragging = ref(false)

const limitLabel = computed(() => formatSize(formats.value.max_bytes))

// See the note on the file input: the extensions alone are too narrow for iOS.
const acceptAttr = computed(() =>
  [...formats.value.extensions, 'application/xml', 'text/xml', 'application/json'].join(','),
)

const submit = async (file: File | undefined) => {
  if (!file || importing.value) return
  const imported = await importFile(file)
  if (imported?.status === 'imported') emit('imported', imported.activity_id)
}

const handlePick = async (event: Event) => {
  const target = event.target as HTMLInputElement
  await submit(target.files?.[0])
  // Clear the input so picking the same file again still fires change — the
  // natural thing to do after a failure the runner has since fixed.
  target.value = ''
}

const handleDrop = async (event: DragEvent) => {
  dragging.value = false
  await submit(event.dataTransfer?.files?.[0])
}

const clear = () => {
  reset()
  if (input.value) input.value.value = ''
}

onMounted(loadFormats)
</script>
