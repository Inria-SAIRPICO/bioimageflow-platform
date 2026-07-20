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
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
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

  it('aborts an active upload and records cancellation without an error', async () => {
    const pending = deferred<any>()
    let signal: AbortSignal | undefined
    mocks.uploadDataset.mockImplementation((_file, options) => {
      signal = options.signal
      signal?.addEventListener('abort', () => pending.reject(new DOMException('Aborted', 'AbortError')))
      return pending.promise
    })
    const store = useDatasetsStore()

    store.queueUploads([new File(['large'], 'large.tif')])
    expect(store.uploads[0].status).toBe('uploading')
    store.cancelUpload(store.uploads[0])

    expect(signal?.aborted).toBe(true)
    await vi.waitFor(() => expect(store.uploads[0].status).toBe('cancelled'))
    expect(store.uploads[0].message).toBe('Cancelled')
  })

  it('cancels queued uploads before they start and can cancel the whole batch', async () => {
    const pending = Array.from({ length: 3 }, () => deferred<any>())
    mocks.uploadDataset.mockImplementation((_file, options) => {
      const request = pending[mocks.uploadDataset.mock.calls.length - 1]
      options.signal?.addEventListener('abort', () => request.reject(new DOMException('Aborted', 'AbortError')))
      return request.promise
    })
    const store = useDatasetsStore()
    store.queueUploads([
      new File(['1'], 'one.tif'),
      new File(['2'], 'two.tif'),
      new File(['3'], 'three.tif'),
      new File(['4'], 'queued.tif'),
    ])

    expect(mocks.uploadDataset).toHaveBeenCalledTimes(3)
    expect(store.uploads[3].status).toBe('queued')
    store.cancelUploads()

    await vi.waitFor(() => expect(store.hasActiveUploads).toBe(false))
    expect(mocks.uploadDataset).toHaveBeenCalledTimes(3)
    expect(store.uploads.every(upload => upload.status === 'cancelled')).toBe(true)
  })

  it('clears completed and cancelled messages while retaining actionable errors', () => {
    const store = useDatasetsStore()
    store.uploads = [
      { id: 'success', batchId: 1, file: new File(['a'], 'a.tif'), loaded: 1, total: 1, status: 'success' },
      { id: 'cancelled', batchId: 1, file: new File(['b'], 'b.tif'), loaded: 0, total: 1, status: 'cancelled' },
      { id: 'error', batchId: 1, file: new File(['c'], 'c.tif'), loaded: 1, total: 1, status: 'error', message: 'No space left on device' },
    ]

    store.clearCompletedUploads()

    expect(store.uploads.map(upload => upload.id)).toEqual(['error'])
    store.dismissUpload(store.uploads[0])
    expect(store.uploads).toEqual([])
  })

  it('keeps server disk-write details available for retry', async () => {
    mocks.uploadDataset.mockResolvedValue({
      uploaded: [],
      errors: [{ filename: 'large.tif', error: 'invalid_file', detail: 'No space left on device' }],
    })
    const store = useDatasetsStore()

    store.queueUploads([new File(['large'], 'large.tif')])

    await vi.waitFor(() => expect(store.uploads[0].status).toBe('error'))
    expect(store.uploads[0].message).toBe('No space left on device')
  })
})
