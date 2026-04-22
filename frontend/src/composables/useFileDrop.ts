import { onMounted, onBeforeUnmount } from 'vue'
import { isDesktop } from '@/utils/nativeDialogs'
import { useDatasetBrowserStore } from '@/stores/datasetBrowser'

/** Window-level file-drop handler — dual behavior per spec §3.13. */

const TOOL_MIME = 'application/bioimageflow-tool'

export interface UseFileDropOptions {
  /**
   * Called with a list of server-side absolute paths when the user drops OS
   * files on the window. In browser mode the paths come from the Dataset
   * Browser modal (after upload). In desktop mode the paths come from
   * pywebview's `File.path` injection.
   */
  onPaths: (paths: string[]) => void
}

/** For test-time injection of a custom path resolver on a `File`. */
function resolveDesktopPath(file: File): string | null {
  // pywebview injects `.path` on dropped files in some builds. Treat absence
  // as "not available" and fall back to the browser-mode upload flow so the
  // user isn't left stranded.
  const maybe = (file as File & { path?: string }).path
  return typeof maybe === 'string' && maybe.length > 0 ? maybe : null
}

export function useFileDrop(options: UseFileDropOptions) {
  const store = useDatasetBrowserStore()

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

  async function onDrop(event: DragEvent) {
    if (isToolDrop(event)) return // palette tool-drop; CanvasView handles it
    if (!hasFiles(event)) return

    event.preventDefault()
    const files = Array.from(event.dataTransfer?.files ?? [])

    if (isDesktop()) {
      const resolved: string[] = []
      const unresolved: File[] = []
      for (const f of files) {
        const p = resolveDesktopPath(f)
        if (p) resolved.push(p)
        else unresolved.push(f)
      }
      if (resolved.length > 0) {
        options.onPaths(resolved)
      }
      // Any files pywebview couldn't give us a path for fall back to the
      // browser-mode upload flow so the user isn't left stranded.
      if (unresolved.length > 0) {
        store.registerCreateFilesNodeHandler(options.onPaths)
        void store.open({
          mode: 'upload-and-pick',
          parameterName: 'drop',
          initialFiles: unresolved,
        })
      }
      return
    }

    // Browser mode: open the Dataset Browser in upload-and-pick mode with the
    // dropped files already queued for upload. The final paths are delivered
    // via `createFilesNode` on the modal.
    store.registerCreateFilesNodeHandler(options.onPaths)
    void store.open({
      mode: 'upload-and-pick',
      parameterName: 'drop',
      initialFiles: files,
    })
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
