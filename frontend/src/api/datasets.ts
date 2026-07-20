import { api } from '@/api/client'

export interface DatasetRecord {
  id: string
  original_filename: string
  display_name: string
  path: string
  size: number
  upload_date: string
  content_type: string | null
  folder_id: string | null
}

export interface DatasetFolderRecord {
  id: string
  name: string
  parent_id: string | null
  created_at: string
}

export interface UploadResponseRecord {
  uploaded: DatasetRecord[]
  errors: Array<{ filename: string; error: string; detail: string }>
}

export interface DatasetSelection {
  dataset_ids: string[]
  folder_ids: string[]
}

export interface UploadProgress { loaded: number; total?: number }
export interface UploadOptions {
  folderId?: string | null
  onProgress?: (progress: UploadProgress) => void
  signal?: AbortSignal
}

export async function listDatasets(): Promise<DatasetRecord[]> {
  return (await api.get<DatasetRecord[]>('/api/v1/datasets')).data
}

export async function listDatasetFolders(): Promise<DatasetFolderRecord[]> {
  return (await api.get<DatasetFolderRecord[]>('/api/v1/datasets/folders')).data
}

export async function uploadDataset(
  file: File,
  options: UploadOptions = {},
): Promise<UploadResponseRecord> {
  const formData = new FormData()
  formData.append('files', file, file.name)
  if (options.folderId) formData.append('folder_id', options.folderId)
  return (await api.post<UploadResponseRecord>('/api/v1/datasets/upload', formData, {
    onUploadProgress: event => options.onProgress?.({ loaded: event.loaded, total: event.total }),
    signal: options.signal,
  })).data
}

export async function createDatasetFolder(
  name: string,
  parentId: string | null,
): Promise<DatasetFolderRecord> {
  return (await api.post<DatasetFolderRecord>('/api/v1/datasets/folders', {
    name, parent_id: parentId,
  })).data
}

export async function updateDatasetFolder(
  id: string,
  changes: { name?: string; parent_id?: string | null },
): Promise<DatasetFolderRecord> {
  return (await api.patch<DatasetFolderRecord>(`/api/v1/datasets/folders/${id}`, changes)).data
}

export async function updateDataset(
  id: string,
  changes: { display_name?: string; folder_id?: string | null },
): Promise<DatasetRecord> {
  return (await api.patch<DatasetRecord>(`/api/v1/datasets/${id}`, changes)).data
}

export async function resolveDatasetSelection(selection: DatasetSelection): Promise<DatasetRecord[]> {
  return (await api.post<DatasetRecord[]>('/api/v1/datasets/actions/resolve', selection)).data
}

export async function previewDatasetDelete(selection: DatasetSelection): Promise<{
  revision: number; dataset_count: number; folder_count: number
}> {
  return (await api.post('/api/v1/datasets/actions/delete-preview', selection)).data
}

export async function deleteDatasetSelection(
  selection: DatasetSelection,
  expectedRevision: number,
): Promise<{
  deleted_dataset_ids: string[]
  deleted_folder_ids: string[]
  errors: Array<{ id: string; detail: string }>
}> {
  return (await api.post('/api/v1/datasets/actions/delete', {
    ...selection, expected_revision: expectedRevision,
  })).data
}

export async function deleteDataset(id: string): Promise<void> {
  await api.delete(`/api/v1/datasets/${id}`)
}
