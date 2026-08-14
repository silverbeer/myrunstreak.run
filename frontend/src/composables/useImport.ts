import { ref } from 'vue'
import { apiCall, apiUpload } from '@/config/api'
import type { ImportFormats, ImportResult } from '@/types/runs'

/**
 * Single activity file import (SB-418) — the UI half of SB-99.
 *
 * The accepted extensions and size cap come from `GET /import/formats` rather
 * than being restated here: the server enforces them either way, and a second
 * hard-coded copy is one that drifts. FALLBACK_FORMATS only covers the window
 * before that call lands (or if it fails), so the picker is never inert.
 */
const FALLBACK_FORMATS: ImportFormats = {
  extensions: ['.gpx', '.json', '.tcx'],
  max_bytes: 10 * 1024 * 1024,
  default_timezone: 'America/New_York',
}

export function useImport() {
  const importing = ref(false)
  const error = ref<string | null>(null)
  const result = ref<ImportResult | null>(null)
  const formats = ref<ImportFormats>(FALLBACK_FORMATS)

  const loadFormats = async (): Promise<void> => {
    try {
      formats.value = await apiCall<ImportFormats>('/import/formats')
    } catch {
      // Non-fatal: the fallback is accurate today, and the server still
      // rejects anything outside its own allowlist.
    }
  }

  /** Client-side check, so a wrong or huge file fails instantly. Null when OK. */
  const validate = (file: File): string | null => {
    const { extensions, max_bytes: maxBytes } = formats.value
    const dot = file.name.lastIndexOf('.')
    const extension = dot === -1 ? '' : file.name.slice(dot).toLowerCase()

    if (!extensions.includes(extension)) {
      return `${extension || 'That file'} can't be imported. Try ${extensions.join(', ')}.`
    }
    if (file.size > maxBytes) {
      const limitMb = Math.round(maxBytes / (1024 * 1024))
      return `That file is ${formatSize(file.size)} — the limit is ${limitMb} MB.`
    }
    if (file.size === 0) {
      return 'That file is empty.'
    }
    return null
  }

  const importFile = async (file: File): Promise<ImportResult | null> => {
    error.value = null
    result.value = null

    const invalid = validate(file)
    if (invalid) {
      error.value = invalid
      return null
    }

    importing.value = true
    try {
      const body = new FormData()
      body.append('file', file, file.name)
      // GPX and TCX record UTC, so the run's date depends on which zone it is
      // read into. The browser knows the runner's; sending it beats the
      // server's America/New_York default for anyone outside that zone.
      body.append('timezone', browserTimezone() ?? formats.value.default_timezone)

      const res = await apiUpload<ImportResult>('/import/activity', body)
      result.value = res
      return res
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Import failed'
      return null
    } finally {
      importing.value = false
    }
  }

  const reset = (): void => {
    error.value = null
    result.value = null
  }

  return { importFile, loadFormats, validate, reset, importing, error, result, formats }
}

export function browserTimezone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null
  } catch {
    return null
  }
}

export function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`
  return `${bytes} bytes`
}
