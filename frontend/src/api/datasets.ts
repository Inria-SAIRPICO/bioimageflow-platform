import { api } from '@/api/client'
import type { Dataset, UploadResponse } from '@/api/types'

export interface UploadProgress {
  loaded: number
  total?: number
}

export interface UploadOptions {
  onProgress?: (progress: UploadProgress) => void
}

export async function listDatasets(): Promise<Dataset[]> {
  const response = await api.get<Dataset[]>('/api/v1/datasets')
  return response.data
}

export async function uploadDataset(
  file: File,
  options: UploadOptions = {},
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('files', file, file.name)

  const response = await api.post<UploadResponse>('/api/v1/datasets/upload', formData, {
    onUploadProgress: (event: { loaded: number; total?: number }) => {
      options.onProgress?.({ loaded: event.loaded, total: event.total })
    },
  })
  return response.data
}

export async function deleteDataset(id: string): Promise<void> {
  await api.delete(`/api/v1/datasets/${id}`)
}
