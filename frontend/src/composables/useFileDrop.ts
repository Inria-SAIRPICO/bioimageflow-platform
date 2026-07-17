import { onMounted, onBeforeUnmount } from 'vue'
import { useDatasetsStore } from '@/stores/datasets'

/** Window-level file-drop handler for managed dataset uploads. */

const TOOL_MIME = 'application/bioimageflow-tool'

export function useFileDrop() {
  const store = useDatasetsStore()

  function isToolDrop(event: DragEvent): boolean {
    return event.dataTransfer?.types.includes(TOOL_MIME) ?? false
  }

  function hasFiles(event: DragEvent): boolean {
    return (event.dataTransfer?.files?.length ?? 0) > 0
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
