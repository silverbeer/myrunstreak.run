import { supabase } from './supabase'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export const getApiBase = (): string => API_BASE

export const apiCall = async <T>(
  path: string,
  options: RequestInit = {}
): Promise<T> => {
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({ message: 'Request failed' }))
    // `detail` may be a string (most 4xx) or a structured object (e.g. the
    // dup-athlete 409, SB-349). Keep the human message on .message, and attach
    // status + parsed body so callers can act on structured errors.
    const detail = body?.detail
    const message =
      (detail && typeof detail === 'object' ? detail.message : detail) ||
      body?.message ||
      `HTTP ${response.status}`
    const err = new Error(message) as Error & { status?: number; body?: unknown }
    err.status = response.status
    err.body = body
    throw err
  }

  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return null as T
  }

  return response.json()
}
