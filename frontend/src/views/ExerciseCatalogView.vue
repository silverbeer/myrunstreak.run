<template>
  <div class="container-app py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Exercise catalog</h1>
      <p class="text-sm text-gray-500 mt-1">
        The shared library plus your own exercises. Search before adding — keep the catalog clean.
      </p>
    </div>

    <div v-if="loading" class="text-sm text-gray-500">Loading catalog…</div>
    <div
      v-else-if="error"
      class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700"
    >
      {{ error }}
    </div>

    <template v-else>
      <ExerciseEditForm
        v-if="editing"
        :exercise="editing"
        class="mb-4"
        @save="onSave"
        @cancel="editing = null"
      />

      <ExercisePicker
        :exercises="exercises"
        :editable-keys="editableKeys"
        mode="manage"
        @create="onCreate"
        @publish="onPublish"
        @edit="startEdit"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ExercisePicker from '@/components/ExercisePicker.vue'
import ExerciseEditForm from '@/components/ExerciseEditForm.vue'
import { useExercises } from '@/composables/useExercises'
import { useRoles } from '@/composables/useCoach'
import { useAuthStore } from '@/stores/auth'
import type { Exercise, ExerciseCreate, ExerciseUpdate } from '@/types/workout'

const router = useRouter()
const { isCoach, isAdmin, loadRoles } = useRoles()
const auth = useAuthStore()
const { exercises, loading, error, load, create, update, publish } = useExercises()

const editing = ref<Exercise | null>(null)

// A coach edits only their own; an admin edits anything (incl. the canonical
// library, owner_id === null). Mirrors the backend permission.
const editableKeys = computed<string[]>(() => {
  const myId = auth.user?.id ?? null
  return exercises.value
    .filter((ex) => isAdmin.value || (!!ex.owner_id && ex.owner_id === myId))
    .map((ex) => ex.key)
})

const startEdit = (ex: Exercise): void => {
  editing.value = ex
}

const onSave = async (patch: ExerciseUpdate): Promise<void> => {
  if (!editing.value) return
  const updated = await update(editing.value.key, patch)
  if (updated) editing.value = null
}

const onCreate = async (payload: ExerciseCreate) => {
  await create(payload)
}
const onPublish = async (key: string) => {
  await publish(key)
}

onMounted(async () => {
  // Coach/admin only — the nav link is hidden for others, but guard direct URLs.
  await loadRoles()
  if (!isCoach.value) {
    router.replace('/dashboard')
    return
  }
  await load()
})
</script>
