import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Dataset, UploadResponse } from '../types'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

import { api } from '@/api/client'
import { listDatasets, uploadDataset, deleteDataset } from '../datasets'

const mockedGet = vi.mocked(api.get)
const mockedPost = vi.mocked(api.post)
const mockedDelete = vi.mocked(api.delete)

beforeEach(() => {
  mockedGet.mockReset()
  mockedPost.mockReset()
  mockedDelete.mockReset()
})

describe('listDatasets', () => {
  it('returns the parsed array', async () => {
    const items: Dataset[] = [
      {
        id: 'd_abc',
        original_filename: 'cells.tif',
        path: '/srv/datasets/20260421T120000_cells.tif',
        size: 1024,
        upload_date: '2026-04-21T12:00:00Z',
        content_type: 'image/tiff',
      },
    ]
    mockedGet.mockResolvedValue({ data: items })

    const result = await listDatasets()

    expect(mockedGet).toHaveBeenCalledWith('/api/v1/datasets')
    expect(result).toEqual(items)
  })
})

describe('uploadDataset', () => {
  it('posts a single-file multipart request and surfaces progress', async () => {
    const response: UploadResponse = {
      uploaded: [
        {
          id: 'd_xyz',
          original_filename: 'cells.tif',
          path: '/srv/datasets/20260421T120000_cells.tif',
          size: 11,
          upload_date: '2026-04-21T12:00:00Z',
          content_type: 'image/tiff',
        },
      ],
      errors: [],
    }
    mockedPost.mockResolvedValue({ data: response })

    const file = new File(['hello world'], 'cells.tif', { type: 'image/tiff' })
    const progressCallback = vi.fn()

    const result = await uploadDataset(file, { onProgress: progressCallback })

    expect(mockedPost).toHaveBeenCalledTimes(1)
    const [url, formData, options] = mockedPost.mock.calls[0]
    expect(url).toBe('/api/v1/datasets/upload')
    expect(formData).toBeInstanceOf(FormData)
    // The multipart field name must be "files" to match the backend `UploadFile` param
    expect((formData as FormData).getAll('files')).toHaveLength(1)
    expect(options).toHaveProperty('onUploadProgress')

    // Simulate axios firing the progress event
    const axiosProgressHandler = (options as { onUploadProgress: (e: { loaded: number; total?: number }) => void }).onUploadProgress
    axiosProgressHandler({ loaded: 5, total: 11 })
    expect(progressCallback).toHaveBeenCalledWith({ loaded: 5, total: 11 })

    expect(result).toEqual(response)
  })

  it('works without a progress callback', async () => {
    mockedPost.mockResolvedValue({ data: { uploaded: [], errors: [] } })

    const file = new File(['x'], 'a.tif')
    await uploadDataset(file)

    expect(mockedPost).toHaveBeenCalledTimes(1)
  })
})

describe('deleteDataset', () => {
  it('sends DELETE and resolves on 204', async () => {
    mockedDelete.mockResolvedValue({ status: 204, data: null })

    await deleteDataset('d_abc')

    expect(mockedDelete).toHaveBeenCalledWith('/api/v1/datasets/d_abc')
  })
})
