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
    const error = await response.json().catch(() => ({ message: 'Request failed' }))
    throw new Error(error.detail || error.message || `HTTP ${response.status}`)
  }

  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return null as T
  }

  return response.json()
}
