import { computed, ref } from 'vue'
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
  file: File
  loaded: number
  total: number
  status: 'queued' | 'uploading' | 'success' | 'error'
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
  let runningUploads = 0
  let pickerPreviousSelection: Record<string, boolean> | null = null
  const queued: Array<{ entry: UploadEntry; folderId: string | null }> = []

  const progress = computed(() => {
    const total = uploads.value.reduce((sum, item) => sum + item.total, 0)
    const loaded = uploads.value.reduce((sum, item) => sum + item.loaded, 0)
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
    for (const file of files) {
      const entry: UploadEntry = {
        id: `upload-${++uploadCounter}`, file, loaded: 0, total: file.size,
        status: 'queued',
      }
      uploads.value.push(entry)
      queued.push({ entry, folderId })
    }
    activate()
    pumpUploads()
  }

  function retryUpload(entry: UploadEntry, folderId: string | null = null) {
    entry.loaded = 0
    entry.status = 'queued'
    entry.message = undefined
    queued.push({ entry, folderId })
    pumpUploads()
  }

  function pumpUploads() {
    while (runningUploads < 3 && queued.length) {
      const next = queued.shift()!
      runningUploads += 1
      next.entry.status = 'uploading'
      void uploadDataset(next.entry.file, {
        folderId: next.folderId,
        onProgress: value => {
          next.entry.loaded = value.loaded
          next.entry.total = value.total ?? next.entry.file.size
        },
      }).then(response => {
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
        next.entry.status = 'error'
        next.entry.message = error instanceof Error ? error.message : 'Upload failed'
      }).finally(() => {
        runningUploads -= 1
        pumpUploads()
      })
    }
  }

  return {
    datasets, folders, selectionKeys, pickerSelectionId, picker, uploads,
    activationRequest, progress, activate, refresh, selectedIds, openPicker,
    finishPicker, queueUploads, retryUpload,
  }
})
