import { supabase } from './supabase'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export const getApiBase = (): string => API_BASE

/** FastAPI's 422 body: `detail` is an array of per-field validation errors. */
type ValidationItem = { loc?: unknown[]; msg?: string }

/**
 * A human message from an error body, or null if it holds nothing readable.
 *
 * `detail` arrives in three shapes: a plain string (most 4xx), an object with
 * `.message` (the structured 409s), and — for 422 — an *array* of validation
 * items. The array case used to fall through to a bare `HTTP 422`, which is
 * what an athlete saw when the print sheet failed (SB-523).
 */
const readableError = (body: unknown): string | null => {
  const detail = (body as { detail?: unknown; message?: unknown })?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail)) {
    const parts = (detail as ValidationItem[])
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : undefined
        return field ? `${String(field)}: ${d.msg ?? 'invalid'}` : d.msg
      })
      .filter(Boolean)
    if (parts.length) return parts.join('; ')
  }
  if (detail && typeof detail === 'object') {
    const msg = (detail as { message?: unknown }).message
    if (typeof msg === 'string' && msg) return msg
  }
  const top = (body as { message?: unknown })?.message
  return typeof top === 'string' && top ? top : null
}

/**
 * Multipart upload (SB-418: activity file import).
 *
 * Separate from `apiCall` because that one always sets
 * `Content-Type: application/json`. A multipart body must NOT carry a
 * hand-written Content-Type — the browser has to set it itself so it can
 * include the boundary, and overriding it makes the server fail to parse.
 */
export const apiUpload = async <T>(path: string, body: FormData): Promise<T> => {
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token

  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${path}`, { method: 'POST', headers, body })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ message: 'Upload failed' }))
    const message = readableError(errorBody) ?? `HTTP ${response.status}`
    const err = new Error(message) as Error & { status?: number; body?: unknown }
    err.status = response.status
    err.body = errorBody
    throw err
  }

  return response.json()
}

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
    // Keep the human message on .message, and attach status + parsed body so
    // callers can act on structured errors. See readableError for the shapes.
    const message = readableError(body) ?? `HTTP ${response.status}`
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
