import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { post: vi.fn() },
}))

import { api } from '@/api/client'
import { useNapariStore, type NapariOpenPayload } from '@/stores/napari'

const payload: NapariOpenPayload = {
  paths: ['/tmp/image.tif'],
  clear_layers: false,
  node_id: 'node-1',
  row: 0,
  col: 'image',
  workflow_name: null,
}

describe('napari store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.post).mockReset()
  })

  it('keeps progress visible until opening completes', async () => {
    let resolveRequest!: () => void
    vi.mocked(api.post).mockReturnValueOnce(new Promise((resolve) => {
      resolveRequest = () => resolve({ data: { status: 'ok' } })
    }))
    const napari = useNapariStore()

    const request = napari.open(payload)

    expect(napari.requestPending).toBe(true)
    expect(napari.phase).toBe('opening')
    expect(api.post).toHaveBeenCalledWith('/api/v1/napari/open', payload)

    resolveRequest()
    await request

    expect(napari.requestPending).toBe(false)
    expect(napari.phase).toBeNull()
  })

  it('clears progress when opening fails', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new Error('launch failed'))
    const napari = useNapariStore()

    await expect(napari.open(payload)).rejects.toThrow('launch failed')

    expect(napari.requestPending).toBe(false)
    expect(napari.phase).toBeNull()
  })
})
