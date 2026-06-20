import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Session, User } from '@supabase/supabase-js'
import { supabase, getOAuthRedirectUrl } from '@/config/supabase'
import { apiCall } from '@/config/api'

export const useAuthStore = defineStore('auth', () => {
  const session = ref<Session | null>(null)
  const user = ref<User | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => !!session.value)

  const setError = (msg: string | null) => { error.value = msg }
  const clearError = () => { error.value = null }

  const initialize = async () => {
    loading.value = true
    try {
      const { data } = await supabase.auth.getSession()
      session.value = data.session
      user.value = data.session?.user ?? null

      supabase.auth.onAuthStateChange((_event, newSession) => {
        session.value = newSession
        user.value = newSession?.user ?? null
      })
    } finally {
      loading.value = false
    }
  }

  const signIn = async (email: string, password: string) => {
    loading.value = true
    clearError()
    try {
      const { data, error: err } = await supabase.auth.signInWithPassword({ email, password })
      if (err) throw err
      session.value = data.session
      user.value = data.user
      return { success: true }
    } catch (err: any) {
      setError(err.message)
      return { success: false, error: err.message }
    } finally {
      loading.value = false
    }
  }

  const signInWithGoogle = async () => {
    loading.value = true
    clearError()
    try {
      const { error: err } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: getOAuthRedirectUrl(),
          queryParams: { access_type: 'offline', prompt: 'consent' },
        },
      })
      if (err) throw err
      return { success: true }
    } catch (err: any) {
      setError(err.message)
      return { success: false, error: err.message }
    } finally {
      loading.value = false
    }
  }

  // Invite-only onboarding (SB-188): redeem a token → backend creates the
  // account + returns a session, which we adopt into the Supabase client so
  // the app is logged straight in. Open signup is intentionally gone.
  const redeemInvite = async (token: string, password: string) => {
    loading.value = true
    clearError()
    try {
      const data = await apiCall<{ access_token: string; refresh_token: string }>(
        '/invites/redeem',
        { method: 'POST', body: JSON.stringify({ token, password }) },
      )
      const { data: sess, error: err } = await supabase.auth.setSession({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      })
      if (err) throw err
      session.value = sess.session
      user.value = sess.user
      return { success: true }
    } catch (err: any) {
      setError(err.message)
      return { success: false, error: err.message }
    } finally {
      loading.value = false
    }
  }

  const signOut = async () => {
    loading.value = true
    try {
      await supabase.auth.signOut()
      session.value = null
      user.value = null
    } finally {
      loading.value = false
    }
  }

  const requestPasswordReset = async (email: string) => {
    loading.value = true
    clearError()
    try {
      await apiCall<{ message: string }>('/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({
          email,
          redirect_to: `${window.location.origin}/auth/reset-password`,
        }),
      })
      return { success: true }
    } catch (err: any) {
      setError(err.message)
      return { success: false, error: err.message }
    } finally {
      loading.value = false
    }
  }

  const applyPasswordReset = async (accessToken: string, newPassword: string) => {
    loading.value = true
    clearError()
    try {
      await apiCall<{ message: string }>('/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({
          access_token: accessToken,
          new_password: newPassword,
        }),
      })
      return { success: true }
    } catch (err: any) {
      setError(err.message)
      return { success: false, error: err.message }
    } finally {
      loading.value = false
    }
  }

  return {
    session,
    user,
    loading,
    error,
    isAuthenticated,
    initialize,
    signIn,
    signInWithGoogle,
    redeemInvite,
    signOut,
    requestPasswordReset,
    applyPasswordReset,
    clearError,
  }
})
