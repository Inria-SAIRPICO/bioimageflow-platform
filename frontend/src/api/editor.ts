import { getActivePinia } from 'pinia'
import { api } from '@/api/client'
import { useCanvasPersistence } from '@/composables/useCanvasPersistence'
import { useGraphSync } from '@/composables/useGraphSync'
import { canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import { useUIStore } from '@/stores/ui'

export type EditorOpenMethod = 'external' | 'embedded' | 'clipboard'

export interface EditorStatus {
  available: boolean
  url: string | null
  version: string | null
  control_available: boolean
  launch_attempted?: boolean
  error_code?: string | null
  error_detail?: string | null
}

export interface EditorOpenResponse {
  opened: boolean
  method: EditorOpenMethod
  url: string | null
  path: string
  project_path?: string | null
  message: string | null
  error_code?: string | null
  error_detail?: string | null
}

type Toast = {
  add: (message: {
    severity: 'success' | 'info' | 'error' | 'warn'
    summary: string
    detail?: string
    life?: number
  }) => void
}

let latestEditorOpenRequestId = 0

function beginEditorOpenRequest(): number {
  latestEditorOpenRequestId += 1
  return latestEditorOpenRequestId
}

function isLatestEditorOpenRequest(requestId?: number): boolean {
  return requestId === undefined || requestId === latestEditorOpenRequestId
}

export interface OpenPathWithEditorOptions {
  showEmbeddedLoading?: boolean
  focusPath?: string
}

export async function getEditorStatus(options: { launch?: boolean } = {}): Promise<EditorStatus> {
  const { data } = options.launch
    ? await api.get<EditorStatus>('/api/v1/editor/status', { params: { launch: true } })
    : await api.get<EditorStatus>('/api/v1/editor/status')
  return data
}

export async function openEditorPath(
  path: string,
  options: { focusPath?: string } = {},
): Promise<EditorOpenResponse> {
  const body = options.focusPath ? { path, focus_path: options.focusPath } : { path }
  const { data } = await api.post<EditorOpenResponse>('/api/v1/editor/open', body)
  return data
}

export async function openEditorTool(
  toolName: string,
  options: { workflowId?: string | null } = {},
): Promise<EditorOpenResponse> {
  const body = options.workflowId
    ? { tool_name: toolName, workflow_id: options.workflowId }
    : { tool_name: toolName }
  const { data } = await api.post<EditorOpenResponse>('/api/v1/editor/open-tool', body)
  return data
}

export function showCodeEditorLoading(path = '', requestId?: number): void {
  window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading', {
    detail: { path, ...(requestId === undefined ? {} : { requestId }) },
  }))
}

export function finishCodeEditorLoading(path?: string, requestId?: number): void {
  window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading-finished', {
    detail: { path, ...(requestId === undefined ? {} : { requestId }) },
  }))
}

export function showCodeEditorDiagnostic(response: EditorOpenResponse): void {
  if (!response.error_code) return
  window.dispatchEvent(new CustomEvent('bif:code-editor-diagnostic', {
    detail: {
      path: response.path,
      error_code: response.error_code,
      error_detail: response.error_detail ?? null,
    },
  }))
}

function editorProjectKey(url: string | null): string | null {
  if (!url) return null
  try {
    const parsed = new URL(url, window.location.href)
    const folder = parsed.searchParams.get('folder')
    return normalizedProjectPath(folder) ?? parsed.origin + parsed.pathname
  } catch {
    return url
  }
}

function normalizedProjectPath(path: string | null | undefined): string | null {
  if (!path) return null
  return path.replace(/\/+$/, '') || path
}

function projectPathFromEditorUrl(url: string | null): string | null {
  if (!url) return null
  try {
    return normalizedProjectPath(new URL(url, window.location.href).searchParams.get('folder'))
  } catch {
    return null
  }
}

function isFolderEditorUrl(url: string | null): boolean {
  if (!url) return false
  try {
    return new URL(url, window.location.href).searchParams.has('folder')
  } catch {
    return url.includes('folder=')
  }
}

export async function openPathWithEditor(
  path: string,
  toast?: Toast | null,
  options?: OpenPathWithEditorOptions,
): Promise<EditorOpenResponse> {
  const showEmbeddedLoading = options?.showEmbeddedLoading === true
  const requestId = beginEditorOpenRequest()
  if (showEmbeddedLoading) {
    showCodeEditorLoading(path, requestId)
  }
  try {
    await flushDraftIfAvailable()
    const response = await openEditorPath(path, { focusPath: options?.focusPath })
    await handleEditorOpenResponse(response, toast, requestId)
    return response
  } finally {
    if (showEmbeddedLoading) {
      finishCodeEditorLoading(path, requestId)
    }
  }
}

export async function openToolWithEditor(
  toolName: string,
  workflowName?: string | null,
  toast?: Toast | null,
  options?: OpenPathWithEditorOptions,
): Promise<EditorOpenResponse> {
  const showEmbeddedLoading = options?.showEmbeddedLoading === true
  const requestId = beginEditorOpenRequest()
  if (showEmbeddedLoading) {
    showCodeEditorLoading('', requestId)
  }
  try {
    await flushDraftIfAvailable()
    const response = await openEditorTool(toolName, { workflowId: workflowName })
    await handleEditorOpenResponse(response, toast, requestId)
    return response
  } finally {
    if (showEmbeddedLoading) {
      finishCodeEditorLoading('', requestId)
    }
  }
}

async function flushDraftIfAvailable(): Promise<void> {
  if (canvasSessionRegistry.sessionCount.value === 0) {
    if (getActivePinia() === undefined) return
    await useWorkflowDraftStore().flush()
    return
  }

  const activeCanvasId = canvasSessionRegistry.activeCanvasId.value
  if (activeCanvasId === null) {
    throw new Error(
      'Select an active workflow or sub-workflow canvas before opening the editor.',
    )
  }
  const session = canvasSessionRegistry.get(activeCanvasId)
  if (session === null) {
    throw new Error('The active canvas session is unavailable. Select its tab and try again.')
  }
  if (session.descriptor.kind === 'root') {
    const fresh = await useCanvasPersistence().ensureFreshForCriticalOperation()
    if (!fresh) {
      throw new Error(
        'Resolve the active workflow conflict before opening the editor.',
      )
    }
    return
  }
  await useGraphSync().flushNow()
}

export async function handleEditorOpenResponse(
  response: EditorOpenResponse,
  toast?: Toast | null,
  requestId?: number,
): Promise<void> {
  if (!isLatestEditorOpenRequest(requestId)) return
  if (response.method === 'external') {
    toast?.add({ severity: 'success', summary: 'Opened in editor', life: 2500 })
    return
  }
  if (response.method === 'embedded' && response.url) {
    const uiStore = useUIStoreIfAvailable()
    const currentUrl = uiStore?.codeEditorUrl ?? null
    const currentPath = uiStore?.codeEditorPath ?? null
    const currentProjectPath = (
      projectPathFromEditorUrl(currentUrl) ?? normalizedProjectPath(uiStore?.codeEditorProjectPath)
    )
    const nextProjectPath = (
      normalizedProjectPath(response.project_path) ?? projectPathFromEditorUrl(response.url)
    )
    const currentProject = currentProjectPath ?? editorProjectKey(currentUrl)
    const nextProject = nextProjectPath ?? editorProjectKey(response.url)
    const preserveCurrentEditorUrl = Boolean(currentUrl) && !isFolderEditorUrl(response.url)
    if (currentProject && nextProject && currentProject === nextProject) {
      if (currentPath === response.path && uiStore?.panels.codeEditor) {
        return
      }
      if (currentPath !== response.path) {
        void focusPathInCurrentEmbeddedEditor(response.path, toast, requestId)
      }
      window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
        detail: {
          url: currentUrl,
          path: response.path,
          projectPath: currentProjectPath ?? nextProjectPath ?? null,
          ...(requestId === undefined ? {} : { requestId }),
        },
      }))
      return
    }
    if (preserveCurrentEditorUrl) {
      if (currentPath === response.path && uiStore?.panels.codeEditor) {
        return
      }
      window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
        detail: {
          url: currentUrl,
          path: response.path,
          projectPath: uiStore?.codeEditorProjectPath ?? null,
          ...(requestId === undefined ? {} : { requestId }),
        },
      }))
      return
    }
    window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
      detail: {
        url: response.url,
        path: response.path,
        projectPath: response.project_path ?? null,
        ...(requestId === undefined ? {} : { requestId }),
      },
    }))
    return
  }
  showCodeEditorDiagnostic(response)
  await navigator.clipboard?.writeText(response.path)
  toast?.add({
    severity: 'info',
    summary: response.message ?? 'Path copied - open in your local editor.',
    life: 3000,
  })
}

async function focusPathInCurrentEmbeddedEditor(
  path: string,
  toast?: Toast | null,
  requestId?: number,
): Promise<void> {
  if (!isLatestEditorOpenRequest(requestId)) return
  try {
    const response = await openEditorPath(path)
    if (!isLatestEditorOpenRequest(requestId)) return
    if (response.opened && response.method === 'embedded') return
    showCodeEditorDiagnostic(response)
    await navigator.clipboard?.writeText(response.path)
    toast?.add({
      severity: 'info',
      summary: response.message ?? 'Path copied - open in your local editor.',
      life: 3000,
    })
  } catch (error) {
    if (!isLatestEditorOpenRequest(requestId)) return
    toast?.add({
      severity: 'warn',
      summary: 'Could not focus file in editor',
      detail: error instanceof Error ? error.message : String(error),
      life: 3000,
    })
  }
}

function useUIStoreIfAvailable(): ReturnType<typeof useUIStore> | null {
  try {
    return useUIStore()
  } catch {
    return null
  }
}
