import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  listDatasets,
  listDatasetFolders,
  uploadDataset,
  type DatasetFolderRecord,
  type DatasetRecord,
} from '@/api/datasets'

export interface UploadEntry {
  id: string
  batchId: number
  file: File
  loaded: number
  total: number
  status: 'queued' | 'uploading' | 'success' | 'error' | 'cancelled'
  message?: string
}

interface PickerRequest {
  parameterName: string
  fileTypes?: string[]
  resolve: (path: string | null) => void
}

export const useDatasetsStore = defineStore('datasets', () => {
  const datasets = ref<DatasetRecord[]>([])
  const folders = ref<DatasetFolderRecord[]>([])
  const selectionKeys = ref<Record<string, boolean>>({})
  const pickerSelectionId = ref<string | null>(null)
  const picker = ref<PickerRequest | null>(null)
  const uploads = ref<UploadEntry[]>([])
  const activationRequest = ref(0)
  let uploadCounter = 0
  let currentBatchId = 0
  let runningUploads = 0
  let pickerPreviousSelection: Record<string, boolean> | null = null
  const queued: Array<{ entry: UploadEntry; folderId: string | null }> = []
  const uploadControllers = new Map<string, AbortController>()

  const hasActiveUploads = computed(() => uploads.value.some(item => (
    item.status === 'queued' || item.status === 'uploading'
  )))

  const hasCompletedUploads = computed(() => uploads.value.some(item => (
    item.status === 'success' || item.status === 'cancelled'
  )))

  const progress = computed(() => {
    const currentUploads = uploads.value.filter(item => item.batchId === currentBatchId)
    const total = currentUploads.reduce((sum, item) => sum + Math.max(item.total, 1), 0)
    const loaded = currentUploads.reduce((sum, item) => {
      if (item.status === 'success' || item.status === 'error' || item.status === 'cancelled') {
        return sum + Math.max(item.total, 1)
      }
      return sum + Math.min(item.loaded, Math.max(item.total, 1))
    }, 0)
    return total ? Math.round((loaded / total) * 100) : 0
  })

  function activate() { activationRequest.value += 1 }

  async function refresh() {
    const [datasetRows, folderRows] = await Promise.all([listDatasets(), listDatasetFolders()])
    datasets.value = datasetRows
    folders.value = folderRows
  }

  function selectedIds(): { dataset_ids: string[]; folder_ids: string[] } {
    const selected = Object.entries(selectionKeys.value).filter(([, value]) => value).map(([key]) => key)
    return {
      dataset_ids: selected.filter(id => id.startsWith('d_')),
      folder_ids: selected.filter(id => id.startsWith('f_')),
    }
  }

  function openPicker(parameterName: string, fileTypes?: string[]): Promise<string | null> {
    if (picker.value) picker.value.resolve(null)
    else pickerPreviousSelection = { ...selectionKeys.value }
    selectionKeys.value = {}
    pickerSelectionId.value = null
    activate()
    return new Promise(resolve => { picker.value = { parameterName, fileTypes, resolve } })
  }

  function finishPicker(path: string | null) {
    const request = picker.value
    picker.value = null
    pickerSelectionId.value = null
    selectionKeys.value = pickerPreviousSelection ?? {}
    pickerPreviousSelection = null
    request?.resolve(path)
  }

  function queueUploads(files: File[], folderId: string | null = null) {
    if (!files.length) return
    const hasActiveBatch = uploads.value.some(item => (
      item.batchId === currentBatchId
      && (item.status === 'queued' || item.status === 'uploading')
    ))
    if (!hasActiveBatch) currentBatchId += 1
    for (const file of files) {
      const entry = reactive<UploadEntry>({
        id: `upload-${++uploadCounter}`, batchId: currentBatchId,
        file, loaded: 0, total: file.size,
        status: 'queued',
      })
      uploads.value.push(entry)
      queued.push({ entry, folderId })
    }
    activate()
    pumpUploads()
  }

  function retryUpload(entry: UploadEntry, folderId: string | null = null) {
    if (entry.status === 'queued' || entry.status === 'uploading') return
    const hasActiveBatch = uploads.value.some(item => (
      item.batchId === currentBatchId
      && (item.status === 'queued' || item.status === 'uploading')
    ))
    if (!hasActiveBatch) currentBatchId += 1
    entry.batchId = currentBatchId
    entry.loaded = 0
    entry.status = 'queued'
    entry.message = undefined
    queued.push({ entry, folderId })
    pumpUploads()
  }

  function cancelUpload(entry: UploadEntry) {
    if (entry.status === 'queued') {
      for (let index = queued.length - 1; index >= 0; index -= 1) {
        if (queued[index].entry.id === entry.id) queued.splice(index, 1)
      }
      entry.status = 'cancelled'
      entry.message = 'Cancelled'
      return
    }
    if (entry.status !== 'uploading') return
    entry.status = 'cancelled'
    entry.message = 'Cancelled'
    uploadControllers.get(entry.id)?.abort()
  }

  function cancelUploads() {
    for (const entry of uploads.value) cancelUpload(entry)
  }

  function clearCompletedUploads() {
    uploads.value = uploads.value.filter(entry => (
      entry.status !== 'success' && entry.status !== 'cancelled'
    ))
  }

  function dismissUpload(entry: UploadEntry) {
    if (entry.status === 'queued' || entry.status === 'uploading') return
    uploads.value = uploads.value.filter(item => item.id !== entry.id)
  }

  function uploadErrorMessage(error: unknown): string {
    if (typeof error === 'object' && error && 'response' in error) {
      const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
      if (typeof detail === 'string') return detail
      if (typeof detail === 'object' && detail && 'detail' in detail) {
        const nested = (detail as { detail?: unknown }).detail
        if (typeof nested === 'string') return nested
      }
    }
    return error instanceof Error ? error.message : 'Upload failed'
  }

  function pumpUploads() {
    while (runningUploads < 3 && queued.length) {
      const next = queued.shift()!
      const controller = new AbortController()
      uploadControllers.set(next.entry.id, controller)
      runningUploads += 1
      next.entry.status = 'uploading'
      void uploadDataset(next.entry.file, {
        folderId: next.folderId,
        signal: controller.signal,
        onProgress: value => {
          if (controller.signal.aborted) return
          next.entry.loaded = value.loaded
          next.entry.total = value.total ?? next.entry.file.size
        },
      }).then(response => {
        if (controller.signal.aborted) return
        if (response.errors.length) {
          next.entry.status = 'error'
          next.entry.message = response.errors[0].detail
          return
        }
        next.entry.loaded = next.entry.total
        next.entry.status = 'success'
        next.entry.message = 'Uploaded'
        for (const dataset of response.uploaded) {
          datasets.value = [dataset, ...datasets.value.filter(item => item.id !== dataset.id)]
          selectionKeys.value[dataset.id] = true
        }
      }).catch(error => {
        if (controller.signal.aborted) {
          if (next.entry.status === 'uploading') {
            next.entry.status = 'cancelled'
            next.entry.message = 'Cancelled'
          }
          return
        }
        next.entry.status = 'error'
        next.entry.message = uploadErrorMessage(error)
      }).finally(() => {
        if (uploadControllers.get(next.entry.id) === controller) {
          uploadControllers.delete(next.entry.id)
        }
        runningUploads -= 1
        pumpUploads()
      })
    }
  }

  return {
    datasets, folders, selectionKeys, pickerSelectionId, picker, uploads,
    activationRequest, progress, hasActiveUploads, hasCompletedUploads,
    activate, refresh, selectedIds, openPicker, finishPicker, queueUploads,
    retryUpload, cancelUpload, cancelUploads, clearCompletedUploads, dismissUpload,
  }
})
