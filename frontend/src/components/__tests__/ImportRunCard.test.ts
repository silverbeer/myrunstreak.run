import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import ImportRunCard from '../ImportRunCard.vue'
import type { ImportResult } from '@/types/runs'

const IMPORTED: ImportResult = {
  status: 'imported',
  activity_id: 'gpx-abc123',
  run_id: '3f0d0f6e-0000-0000-0000-000000000000',
  distance_km: 8.05,
  duration_seconds: 2700,
  start_date_time_local: '2026-08-10T07:15:00-04:00',
  has_track: true,
}

// One shared harness the component's useImport() resolves to, so a test can
// drive the outcome (imported / duplicate / rejected) without any HTTP.
const importing = ref(false)
const error = ref<string | null>(null)
const result = ref<ImportResult | null>(null)
const importFile = vi.fn()
const loadFormats = vi.fn()

vi.mock('@/composables/useImport', async () => {
  const actual = await vi.importActual<typeof import('@/composables/useImport')>(
    '@/composables/useImport'
  )
  return {
    ...actual,
    useImport: () => ({
      importFile,
      loadFormats,
      validate: vi.fn(),
      reset: () => {
        error.value = null
        result.value = null
      },
      importing,
      error,
      result,
      formats: ref({
        extensions: ['.gpx', '.json', '.tcx'],
        max_bytes: 10 * 1024 * 1024,
        default_timezone: 'America/New_York',
      }),
    }),
  }
})

vi.mock('@/composables/useUserPreferences', () => ({
  useUserPreferences: () => ({ unit: ref('mi') }),
}))

const RouterLinkStub = {
  props: ['to'],
  template: '<a><slot /></a>',
}

const mountCard = () =>
  mount(ImportRunCard, { global: { stubs: { RouterLink: RouterLinkStub } } })

const file = (name: string): File => new File(['x'], name)

/** Fire the file input's change event with a chosen file, as the picker does. */
const pick = async (w: ReturnType<typeof mountCard>, chosen: File) => {
  const input = w.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [chosen], configurable: true })
  await input.trigger('change')
  await flushPromises()
}

describe('ImportRunCard', () => {
  beforeEach(() => {
    importing.value = false
    error.value = null
    result.value = null
    importFile.mockReset()
    loadFormats.mockReset()
  })

  it('states the accepted formats and the size cap', () => {
    const w = mountCard()
    expect(w.text()).toContain('.gpx, .json, .tcx')
    expect(w.text()).toContain('10.0 MB')
    // Broader than the extension list on purpose: iOS greys out files whose
    // extension it can't map to a UTI, which would make .tcx unpickable.
    const accept = w.find('input[type="file"]').attributes('accept') ?? ''
    expect(accept).toContain('.gpx')
    expect(accept).toContain('.tcx')
    expect(accept).toContain('application/xml')
  })

  it('asks the server what it accepts on mount', () => {
    mountCard()
    expect(loadFormats).toHaveBeenCalled()
  })

  it('uploads the picked file and shows the imported run', async () => {
    importFile.mockImplementation(async () => {
      result.value = IMPORTED
      return IMPORTED
    })
    const w = mountCard()

    await pick(w, file('run.gpx'))

    expect(importFile).toHaveBeenCalledWith(expect.any(File))
    expect(w.text()).toContain('Run imported')
    expect(w.text()).toContain('5.00 mi') // 8.05 km, shown in the user's unit
    expect(w.emitted('imported')?.[0]).toEqual(['gpx-abc123'])
    expect(w.findComponent(RouterLinkStub).props('to')).toEqual({
      name: 'run-detail',
      params: { activityId: 'gpx-abc123' },
    })
  })

  it('reads a re-upload as already imported, not a failure', async () => {
    const duplicate = { ...IMPORTED, status: 'duplicate' as const }
    importFile.mockImplementation(async () => {
      result.value = duplicate
      return duplicate
    })
    const w = mountCard()

    await pick(w, file('run.gpx'))

    expect(w.text()).toContain('Already imported')
    expect(w.text()).not.toContain('failed')
    // Still links to the run it matched.
    expect(w.findComponent(RouterLinkStub).exists()).toBe(true)
    // A duplicate is not a new run, so nothing to tell the parent about.
    expect(w.emitted('imported')).toBeUndefined()
  })

  it('shows a rejected file type as an error with a retry', async () => {
    importFile.mockImplementation(async () => {
      error.value = ".png can't be imported. Try .gpx, .json, .tcx."
      return null
    })
    const w = mountCard()

    await pick(w, file('photo.png'))

    expect(w.find('[role="alert"]').text()).toContain("can't be imported")
    expect(w.text()).toContain('Try another file')
  })

  it('shows the parse failure reason the server gave', async () => {
    importFile.mockImplementation(async () => {
      error.value = 'Trackpoints carry no timestamps, so the run has no duration.'
      return null
    })
    const w = mountCard()

    await pick(w, file('bad.gpx'))

    expect(w.find('[role="alert"]').text()).toContain('no timestamps')
  })

  it('notes when an imported run has no GPS track', async () => {
    const noTrack = { ...IMPORTED, has_track: false }
    importFile.mockImplementation(async () => {
      result.value = noTrack
      return noTrack
    })
    const w = mountCard()

    await pick(w, file('treadmill.tcx'))

    expect(w.text()).toContain('no GPS track')
  })

  it('clears the outcome so another file can be imported', async () => {
    importFile.mockImplementation(async () => {
      result.value = IMPORTED
      return IMPORTED
    })
    const w = mountCard()
    await pick(w, file('run.gpx'))
    expect(w.text()).toContain('Run imported')

    await w.get('button').trigger('click')
    await flushPromises()

    expect(w.text()).not.toContain('Run imported')
  })

  it('accepts a dropped file', async () => {
    importFile.mockImplementation(async () => {
      result.value = IMPORTED
      return IMPORTED
    })
    const w = mountCard()

    await w.find('label').trigger('drop', { dataTransfer: { files: [file('run.gpx')] } })
    await flushPromises()

    expect(importFile).toHaveBeenCalledWith(expect.any(File))
    expect(w.text()).toContain('Run imported')
  })

  it('ignores a second file while one is uploading', async () => {
    importing.value = true
    const w = mountCard()

    await pick(w, file('run.gpx'))

    expect(importFile).not.toHaveBeenCalled()
    expect(w.text()).toContain('Importing…')
  })
})
