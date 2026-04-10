/**
 * Native file dialog bridge for pywebview desktop mode.
 *
 * When running inside pywebview, calls are forwarded to the native API at
 * `window.pywebview.api`. In browser-only dev mode the functions fall back
 * to returning `null` / empty arrays (or using `prompt()` where appropriate).
 */

declare global {
  interface Window {
    pywebview?: {
      api: {
        select_file: (title: string, fileTypes: string[]) => Promise<string | null>
        select_files: (title: string, fileTypes: string[]) => Promise<string[]>
        select_folder: (title: string) => Promise<string | null>
        save_file: (
          title: string,
          fileTypes: string[],
          defaultName: string,
        ) => Promise<string | null>
        set_title: (title: string) => Promise<void>
        reveal_path: (path: string) => Promise<void>
      }
    }
  }
}

/** True when running inside a pywebview window. */
export function isDesktop(): boolean {
  return typeof window !== 'undefined' && window.pywebview?.api !== undefined
}

/**
 * Open a native file picker and return the selected path, or `null` if
 * cancelled. Falls back to `prompt()` in browser mode.
 */
export async function selectFile(
  title = 'Select File',
  fileTypes: string[] = [],
): Promise<string | null> {
  if (isDesktop()) {
    return window.pywebview!.api.select_file(title, fileTypes)
  }
  return prompt(title) ?? null
}

/**
 * Open a native file picker allowing multiple selection. Falls back to an
 * empty array in browser mode.
 */
export async function selectFiles(
  title = 'Select Files',
  fileTypes: string[] = [],
): Promise<string[]> {
  if (isDesktop()) {
    return window.pywebview!.api.select_files(title, fileTypes)
  }
  return []
}

/**
 * Open a native folder picker. Falls back to `prompt()` in browser mode.
 */
export async function selectFolder(title = 'Select Folder'): Promise<string | null> {
  if (isDesktop()) {
    return window.pywebview!.api.select_folder(title)
  }
  return prompt(title) ?? null
}

/**
 * Open a native save dialog. Falls back to `prompt()` in browser mode.
 */
export async function saveFile(
  title = 'Save File',
  fileTypes: string[] = [],
  defaultName = '',
): Promise<string | null> {
  if (isDesktop()) {
    return window.pywebview!.api.save_file(title, fileTypes, defaultName)
  }
  return prompt(title, defaultName) ?? null
}

/**
 * Set the native window title. No-op in browser mode.
 */
export async function setTitle(title: string): Promise<void> {
  if (isDesktop()) {
    return window.pywebview!.api.set_title(title)
  }
}

/**
 * Update the window title based on the current workflow name and unsaved
 * changes state.
 *
 * Format:
 * - No workflow: `"BioImageFlow"`
 * - With workflow: `"BioImageFlow — My Workflow"`
 * - With unsaved changes: `"BioImageFlow — My Workflow *"`
 *
 * Silently skipped in browser mode (no pywebview).
 */
export async function updateWindowTitle(
  workflowName?: string | null,
  hasUnsavedChanges?: boolean,
): Promise<void> {
  let title = 'BioImageFlow'
  if (workflowName) {
    title = `BioImageFlow \u2014 ${workflowName}`
    if (hasUnsavedChanges) {
      title += ' *'
    }
  }
  await setTitle(title)
}

/**
 * Reveal a path in the system file browser. No-op in browser mode.
 */
export async function revealPath(path: string): Promise<void> {
  if (isDesktop()) {
    return window.pywebview!.api.reveal_path(path)
  }
}
