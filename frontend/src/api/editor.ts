import { api } from '@/api/client'
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

export function showCodeEditorLoading(path = ''): void {
  window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading', {
    detail: { path },
  }))
}

export function finishCodeEditorLoading(path?: string): void {
  window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading-finished', {
    detail: { path },
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
    return folder ? `folder:${folder}` : parsed.origin + parsed.pathname
  } catch {
    return url
  }
}

export async function openPathWithEditor(
  path: string,
  toast?: Toast | null,
  options?: OpenPathWithEditorOptions,
): Promise<EditorOpenResponse> {
  const showEmbeddedLoading = options?.showEmbeddedLoading === true
  if (showEmbeddedLoading) {
    showCodeEditorLoading(path)
  }
  try {
    await flushDraftIfAvailable()
    const response = await openEditorPath(path, { focusPath: options?.focusPath })
    await handleEditorOpenResponse(response, toast)
    return response
  } finally {
    if (showEmbeddedLoading) {
      finishCodeEditorLoading(path)
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
  if (showEmbeddedLoading) {
    showCodeEditorLoading()
  }
  try {
    await flushDraftIfAvailable()
    const response = await openEditorTool(toolName, { workflowId: workflowName })
    await handleEditorOpenResponse(response, toast)
    return response
  } finally {
    if (showEmbeddedLoading) {
      finishCodeEditorLoading()
    }
  }
}

async function flushDraftIfAvailable(): Promise<void> {
  try {
    await useWorkflowDraftStore().flush()
  } catch {
    // Unit tests and non-app callers may not have an active Pinia instance.
    // Opening the editor should still work; the in-app path flushes drafts.
  }
}

export async function handleEditorOpenResponse(
  response: EditorOpenResponse,
  toast?: Toast | null,
): Promise<void> {
  if (response.method === 'external') {
    toast?.add({ severity: 'success', summary: 'Opened in editor', life: 2500 })
    return
  }
  if (response.method === 'embedded' && response.url) {
    const uiStore = useUIStoreIfAvailable()
    const currentUrl = uiStore?.codeEditorUrl ?? null
    const currentPath = uiStore?.codeEditorPath ?? null
    const currentProject = editorProjectKey(currentUrl)
    const nextProject = editorProjectKey(response.url)
    if (currentProject && nextProject && currentProject === nextProject) {
      if (currentPath !== response.path) {
        void focusPathInCurrentEmbeddedEditor(response.path, toast)
      }
      window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
        detail: { url: currentUrl, path: response.path },
      }))
      return
    }
    window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
      detail: { url: response.url, path: response.path },
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
): Promise<void> {
  try {
    const response = await openEditorPath(path)
    if (response.opened && response.method === 'embedded') return
    showCodeEditorDiagnostic(response)
    await navigator.clipboard?.writeText(response.path)
    toast?.add({
      severity: 'info',
      summary: response.message ?? 'Path copied - open in your local editor.',
      life: 3000,
    })
  } catch (error) {
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
