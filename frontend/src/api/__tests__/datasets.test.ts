import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

import { api } from '@/api/client'
import {
  listDatasets,
  uploadDataset,
  deleteDataset,
  type DatasetRecord,
  type UploadResponseRecord,
} from '../datasets'

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
    const items: DatasetRecord[] = [
      {
        id: 'd_abc',
        original_filename: 'cells.tif',
        display_name: 'Cells',
        path: '/srv/datasets/20260421T120000_cells.tif',
        size: 1024,
        upload_date: '2026-04-21T12:00:00Z',
        content_type: 'image/tiff',
        folder_id: null,
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
    const response: UploadResponseRecord = {
      uploaded: [
        {
          id: 'd_xyz',
          original_filename: 'cells.tif',
          display_name: 'Cells',
          path: '/srv/datasets/20260421T120000_cells.tif',
          size: 11,
          upload_date: '2026-04-21T12:00:00Z',
          content_type: 'image/tiff',
          folder_id: 'f_images',
        },
      ],
      errors: [],
    }
    mockedPost.mockResolvedValue({ data: response })

    const file = new File(['hello world'], 'cells.tif', { type: 'image/tiff' })
    const progressCallback = vi.fn()
    const controller = new AbortController()

    const result = await uploadDataset(file, {
      folderId: 'f_images',
      onProgress: progressCallback,
      signal: controller.signal,
    })

    expect(mockedPost).toHaveBeenCalledTimes(1)
    const [url, formData, options] = mockedPost.mock.calls[0]
    expect(url).toBe('/api/v1/datasets/upload')
    expect(formData).toBeInstanceOf(FormData)
    // The multipart field name must be "files" to match the backend `UploadFile` param
    expect((formData as FormData).getAll('files')).toHaveLength(1)
    expect((formData as FormData).get('folder_id')).toBe('f_images')
    expect(options).toHaveProperty('onUploadProgress')
    expect(options).toHaveProperty('signal', controller.signal)

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
