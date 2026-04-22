import { defineStore } from 'pinia'
import { ref } from 'vue'

export type DatasetBrowserMode = 'pick' | 'upload-and-pick'

export interface DatasetBrowserOpenOptions {
  mode: DatasetBrowserMode
  parameterName: string
  fileTypeFilter?: string[]
  initialFiles?: File[]
}

export type CreateFilesNodeHandler = (paths: string[]) => void

interface PendingResolver {
  resolve: (path: string | null) => void
  options: DatasetBrowserOpenOptions
}

/**
 * Pinia store owning the Dataset Browser modal's open/close state.
 *
 * Holds at most one pending resolver at a time. Re-entering cancels the
 * previous invocation (resolves its promise with null) and takes over, so
 * callers never need try/catch — newest request wins.
 */
export const useDatasetBrowserStore = defineStore('datasetBrowser', () => {
  const isOpen = ref(false)
  const options = ref<DatasetBrowserOpenOptions | null>(null)
  let pending: PendingResolver | null = null

  /** Default handler: no-op unless the host (App.vue) provides one. */
  const createFilesNodeHandler = ref<CreateFilesNodeHandler>(() => {})

  function open(opts: DatasetBrowserOpenOptions): Promise<string | null> {
    // Re-entry: cancel the previous pending resolver with null.
    if (pending) {
      pending.resolve(null)
      pending = null
    }
    options.value = opts
    isOpen.value = true
    return new Promise<string | null>((resolve) => {
      pending = { resolve, options: opts }
    })
  }

  function resolve(path: string | null) {
    const p = pending
    pending = null
    isOpen.value = false
    if (p) p.resolve(path)
  }

  function onSelect(path: string) {
    resolve(path)
  }

  function onClose() {
    resolve(null)
  }

  function onCreateFilesNode(paths: string[]) {
    createFilesNodeHandler.value(paths)
    resolve(null)
  }

  function registerCreateFilesNodeHandler(handler: CreateFilesNodeHandler) {
    createFilesNodeHandler.value = handler
  }

  return {
    isOpen,
    options,
    open,
    onSelect,
    onClose,
    onCreateFilesNode,
    registerCreateFilesNodeHandler,
  }
})
