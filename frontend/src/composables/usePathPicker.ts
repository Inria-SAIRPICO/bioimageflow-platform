import { isDesktop, selectFile, selectFolder } from '@/utils/nativeDialogs'
import { useDatasetsStore } from '@/stores/datasets'

export interface PickFileOptions {
  parameterName: string
  fileTypes?: string[]
}

export class BrowserModeUnsupported extends Error {
  constructor(message = 'Folder selection is not supported in browser mode') {
    super(message)
    this.name = 'BrowserModeUnsupported'
  }
}

/**
 * Single choke point that routes Path-picking between pywebview native dialogs
 * (desktop runtime) and the Datasets panel (browser runtime).
 *
 * Callers never need try/catch for re-entry — newest request wins (the store
 * cancels the previous pending resolver with null).
 */
export function usePathPicker() {
  const store = useDatasetsStore()

  async function pickFile(opts: PickFileOptions): Promise<string | null> {
    if (isDesktop()) {
      return selectFile(`Select file for: ${opts.parameterName}`, opts.fileTypes ?? [])
    }
    return store.openPicker(opts.parameterName, opts.fileTypes)
  }

  async function pickFolder(opts: PickFileOptions): Promise<string | null> {
    if (isDesktop()) {
      return selectFolder(`Select folder for: ${opts.parameterName}`)
    }
    // Browser mode does not support folder picking per spec §3.5.3.
    // Callers are expected to hide the Folder button in browser mode; a call
    // here indicates a bug worth surfacing loudly.
    throw new BrowserModeUnsupported()
  }

  return { pickFile, pickFolder, isDesktop }
}
