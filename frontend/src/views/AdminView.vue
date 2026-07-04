<template>
  <div class="container-app py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Admin</h1>
      <p class="text-sm text-gray-500 mt-1">Issue coach invites and review issued invites.</p>
    </div>

    <!-- Issue a coach invite -->
    <div class="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4 mb-6">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-gray-400">Invite a coach</h2>
      <form class="flex flex-wrap items-center gap-2" @submit.prevent="doInvite">
        <input
          v-model="inviteEmail"
          type="email"
          required
          placeholder="coach's email"
          class="form-input flex-1 min-w-48"
        />
        <button type="submit" :disabled="inviting" class="btn-primary text-sm">
          {{ inviting ? 'Inviting…' : 'Invite coach' }}
        </button>
      </form>

      <div
        v-if="inviteLink"
        class="text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded-lg p-3"
      >
        <p class="mb-1 font-medium text-gray-700">Send this link:</p>
        <div class="flex items-center gap-2">
          <code class="flex-1 break-all">{{ inviteLink }}</code>
          <button type="button" class="btn-secondary text-xs" @click="copy(inviteLink)">
            {{ copiedLink === inviteLink ? 'Copied' : 'Copy' }}
          </button>
        </div>
      </div>

      <div
        v-if="error"
        class="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2"
      >
        {{ error }}
      </div>
    </div>

    <!-- Issued invites -->
    <div class="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-gray-400 mb-4">
        Issued invites
      </h2>

      <div v-if="loading" class="space-y-2">
        <div v-for="i in 3" :key="i" class="h-10 bg-gray-50 rounded-lg animate-pulse" />
      </div>

      <p v-else-if="invites.length === 0" class="text-sm text-gray-500">No invites issued yet.</p>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-left text-xs uppercase tracking-wide text-gray-400 border-b border-gray-100">
            <th class="py-2 pr-2 font-medium">Email</th>
            <th class="py-2 px-2 font-medium">Role</th>
            <th class="py-2 px-2 font-medium">Status</th>
            <th class="py-2 px-2 font-medium">Expires</th>
            <th class="py-2 pl-2 font-medium text-right">Link</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="inv in invites" :key="inv.id" class="border-b border-gray-50 last:border-0">
            <td class="py-2 pr-2 text-gray-800 break-all">{{ inv.email }}</td>
            <td class="py-2 px-2 text-gray-600">{{ inv.grant_role ?? 'athlete' }}</td>
            <td class="py-2 px-2">
              <span :class="statusClass(inv)">{{ statusLabel(inv) }}</span>
            </td>
            <td class="py-2 px-2 text-gray-500 whitespace-nowrap">{{ formatDate(inv.expires_at) }}</td>
            <td class="py-2 pl-2 text-right">
              <button
                v-if="statusLabel(inv) === 'Pending'"
                type="button"
                class="btn-secondary text-xs"
                @click="copy(linkFor(inv))"
              >
                {{ copiedLink === linkFor(inv) ? 'Copied' : 'Copy' }}
              </button>
              <span v-else class="text-gray-300">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { inviteCoach, listInvites, useRoles } from '@/composables/useCoach'
import type { Invite } from '@/types/coach'

const router = useRouter()
const { isAdmin, loadRoles } = useRoles()

const inviteEmail = ref('')
const inviting = ref(false)
const inviteLink = ref('')
const copiedLink = ref('')

const invites = ref<Invite[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const linkFor = (inv: Invite): string => `${window.location.origin}/signup?invite=${inv.token}`

const copy = async (text: string) => {
  await navigator.clipboard?.writeText(text)
  copiedLink.value = text
  setTimeout(() => (copiedLink.value = ''), 2000)
}

const statusLabel = (inv: Invite): string => {
  if (inv.redeemed_at) return 'Redeemed'
  if (new Date(inv.expires_at).getTime() < Date.now()) return 'Expired'
  return 'Pending'
}

const statusClass = (inv: Invite): string => {
  const base = 'inline-block px-1.5 py-0.5 rounded text-[10px] font-medium '
  const s = statusLabel(inv)
  if (s === 'Redeemed') return base + 'bg-green-100 text-green-700'
  if (s === 'Expired') return base + 'bg-gray-100 text-gray-500'
  return base + 'bg-blue-100 text-blue-700'
}

const formatDate = (iso: string): string =>
  new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

const loadList = async () => {
  loading.value = true
  error.value = null
  try {
    invites.value = await listInvites()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load invites'
  } finally {
    loading.value = false
  }
}

const doInvite = async () => {
  inviting.value = true
  error.value = null
  inviteLink.value = ''
  try {
    const invite = await inviteCoach(inviteEmail.value)
    inviteLink.value = linkFor(invite)
    inviteEmail.value = ''
    await loadList()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to create invite'
  } finally {
    inviting.value = false
  }
}

onMounted(async () => {
  // Admin-only page: the nav link is hidden for non-admins, but guard direct
  // URL access too. Roles are cached app-wide; refetch to be safe, then bounce.
  await loadRoles()
  if (!isAdmin.value) {
    router.replace('/dashboard')
    return
  }
  await loadList()
})
</script>
