<template>
  <button
    v-if="mode === 'compact'"
    @click="handleSync"
    :disabled="syncing"
    :title="tooltip"
    class="text-gray-500 hover:text-brand-600 disabled:text-gray-300 disabled:cursor-not-allowed transition p-2"
    aria-label="Sync runs"
  >
    <svg
      class="w-5 h-5"
      :class="{ 'animate-spin': syncing }"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  </button>

  <div v-else class="flex items-center gap-3">
    <button
      @click="handleSync"
      :disabled="syncing"
      class="btn-primary inline-flex items-center gap-2"
    >
      <svg
        class="w-4 h-4"
        :class="{ 'animate-spin': syncing }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
        />
      </svg>
      {{ syncing ? 'Syncing…' : 'Sync now' }}
    </button>
    <span class="text-xs text-gray-500">
      Last synced: {{ formatRelativeTime(lastSyncedAt) }}
    </span>
    <span v-if="error" class="text-xs text-red-600">{{ error }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSync } from '@/composables/useSync'
import { formatRelativeTime } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    mode?: 'full' | 'compact'
  }>(),
  { mode: 'full' },
)

const emit = defineEmits<{
  synced: []
}>()

const { sync, syncing, error, lastSyncedAt } = useSync()

const tooltip = computed(() =>
  syncing.value ? 'Syncing…' : `Sync runs (last: ${formatRelativeTime(lastSyncedAt.value)})`,
)

const handleSync = async () => {
  const result = await sync()
  if (result) emit('synced')
}

// Surface mode for IDE clarity (silences unused warning even though template uses it)
void props.mode
</script>
