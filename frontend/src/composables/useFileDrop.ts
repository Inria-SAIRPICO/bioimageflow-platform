import { onMounted, onBeforeUnmount } from 'vue'
import { useDatasetsStore } from '@/stores/datasets'
import { useErrorReporting } from '@/composables/useErrorReporting'

/** Window-level file-drop handler for managed dataset uploads. */

const TOOL_MIME = 'application/bioimageflow-tool'

interface DroppedFileSystemEntry {
  isDirectory: boolean
  name?: string
}

type DirectoryAwareDataTransferItem = DataTransferItem & {
  getAsEntry?: () => DroppedFileSystemEntry | null
  webkitGetAsEntry?: () => DroppedFileSystemEntry | null
}

export function useFileDrop() {
  const store = useDatasetsStore()
  const { reportError } = useErrorReporting()

  function isToolDrop(event: DragEvent): boolean {
    return event.dataTransfer?.types.includes(TOOL_MIME) ?? false
  }

  function hasFiles(event: DragEvent): boolean {
    const transfer = event.dataTransfer
    return (transfer?.files?.length ?? 0) > 0
      || Array.from(transfer?.items ?? []).some(item => item.kind === 'file')
      || transfer?.types.includes('Files') === true
  }

  function droppedDirectoryNames(event: DragEvent): string[] {
    const items = Array.from(event.dataTransfer?.items ?? [])
    return items.flatMap((item, index) => {
      if (item.kind !== 'file') return []
      const directoryAwareItem = item as DirectoryAwareDataTransferItem
      const entry = directoryAwareItem.getAsEntry?.()
        ?? directoryAwareItem.webkitGetAsEntry?.()
      if (!entry?.isDirectory) return []
      return [entry.name || event.dataTransfer?.files[index]?.name || 'Unnamed folder']
    })
  }

  function reportDirectoryDrop(names: string[]): void {
    const detail = names.length === 1
      ? `Folder "${names[0]}" cannot be uploaded. Drop files instead.`
      : `Folders cannot be uploaded (${names.join(', ')}). Drop files instead.`
    reportError({
      kind: 'dataset_upload_rejected',
      detail,
      alwaysToast: true,
    })
  }

  function onDragOver(event: DragEvent) {
    // Always prevent default to stop the browser from navigating to the dropped
    // file (which is the default behaviour for file drops on <html>).
    if (hasFiles(event) && !isToolDrop(event)) {
      event.preventDefault()
    }
  }

  function onDrop(event: DragEvent) {
    if (isToolDrop(event)) return // palette tool-drop; CanvasView handles it
    if (!hasFiles(event)) return

    event.preventDefault()
    const directoryNames = droppedDirectoryNames(event)
    if (directoryNames.length > 0) {
      reportDirectoryDrop(directoryNames)
      return
    }
    const files = Array.from(event.dataTransfer?.files ?? [])

    store.queueUploads(files)
  }

  onMounted(() => {
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('drop', onDrop)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('dragover', onDragOver)
    window.removeEventListener('drop', onDrop)
  })

  return { onDragOver, onDrop }
}
