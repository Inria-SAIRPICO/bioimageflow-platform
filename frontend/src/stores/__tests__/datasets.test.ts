import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mocks = vi.hoisted(() => ({
  uploadDataset: vi.fn(),
}))

vi.mock('@/api/datasets', () => ({
  listDatasets: vi.fn().mockResolvedValue([]),
  listDatasetFolders: vi.fn().mockResolvedValue([]),
  uploadDataset: mocks.uploadDataset,
}))

import { useDatasetsStore } from '../datasets'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(resolvePromise => { resolve = resolvePromise })
  return { promise, resolve }
}

describe('datasets upload progress', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('tracks the current upload batch instead of retaining earlier batch weight', async () => {
    const first = deferred<any>()
    const second = deferred<any>()
    mocks.uploadDataset
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const store = useDatasetsStore()

    store.queueUploads([new File(['first'], 'first.tif')])
    first.resolve({ uploaded: [], errors: [] })
    await first.promise
    await vi.waitFor(() => expect(store.progress).toBe(100))

    store.queueUploads([new File(['second'], 'second.tif')])
    expect(store.progress).toBe(0)
    second.resolve({ uploaded: [], errors: [] })
    await second.promise
    await vi.waitFor(() => expect(store.uploads[1].status).toBe('success'))
    expect(store.uploads.map(upload => upload.batchId)).toEqual([1, 2])
    await vi.waitFor(() => expect(store.progress).toBe(100))
  })

  it('keeps existing selections and selects newly uploaded files', async () => {
    const uploaded = {
      id: 'd_new', original_filename: 'new.tif', display_name: 'new.tif',
      path: '/managed/new.tif', size: 3, upload_date: '2026-01-01T00:00:00Z',
      content_type: 'image/tiff', folder_id: null,
    }
    mocks.uploadDataset.mockResolvedValue({ uploaded: [uploaded], errors: [] })
    const store = useDatasetsStore()
    store.selectionKeys = { d_existing: true }

    store.queueUploads([new File(['new'], 'new.tif')])
    await vi.waitFor(() => expect(store.uploads[0].status).toBe('success'))

    expect(store.selectionKeys).toEqual({ d_existing: true, d_new: true })
  })
})
