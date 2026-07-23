import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AudioLog from '../AudioLog.vue'

const apiCall = vi.fn()
vi.mock('@/config/api', () => ({ apiCall: (...a: unknown[]) => apiCall(...a) }))

beforeEach(() => apiCall.mockReset())

const mountLog = (props: Record<string, unknown> = {}) =>
  mount(AudioLog, {
    props: { activityId: 'act-1', audioType: null, audioNote: null, ...props },
  })

describe('AudioLog', () => {
  it('offers all five categories', () => {
    const w = mountLog()
    const labels = w.findAll('button').map((b) => b.text().replace(/\s+/g, ' ').trim())
    for (const l of ['Podcast', 'Music', 'Audiobook', 'Other', 'None']) {
      expect(labels.some((x) => x.includes(l))).toBe(true)
    }
  })

  it('Save is disabled until something changes', async () => {
    const w = mountLog()
    const save = w.findAll('button').find((b) => b.text() === 'Save')!
    expect(save.attributes('disabled')).toBeDefined()
    await w.findAll('button').find((b) => b.text().includes('Podcast'))!.trigger('click')
    expect(save.attributes('disabled')).toBeUndefined()
  })

  it('PATCHes the selected type + note on save', async () => {
    apiCall.mockResolvedValue({ audio_type: 'podcast', audio_note: 'Noah Kahan playlist today' })
    const w = mountLog()
    await w.findAll('button').find((b) => b.text().includes('Podcast'))!.trigger('click')
    await w.find('input').setValue('Noah Kahan playlist today')
    await w.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()

    expect(apiCall).toHaveBeenCalledWith('/runs/act-1/audio', {
      method: 'PATCH',
      body: JSON.stringify({ audio_type: 'podcast', audio_note: 'Noah Kahan playlist today' }),
    })
    expect(w.text()).toContain('Saved')
  })

  it('clicking the active category again clears it', async () => {
    const w = mountLog({ audioType: 'music' })
    // Re-selecting the saved value makes it dirty (music -> null), enabling Save.
    await w.findAll('button').find((b) => b.text().includes('Music'))!.trigger('click')
    const save = w.findAll('button').find((b) => b.text() === 'Save')!
    expect(save.attributes('disabled')).toBeUndefined()
  })

  it('sends audio_note null when the note is blank', async () => {
    apiCall.mockResolvedValue({ audio_type: 'music', audio_note: null })
    const w = mountLog()
    await w.findAll('button').find((b) => b.text().includes('Music'))!.trigger('click')
    await w.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    expect(apiCall).toHaveBeenCalledWith('/runs/act-1/audio', {
      method: 'PATCH',
      body: JSON.stringify({ audio_type: 'music', audio_note: null }),
    })
  })
})
