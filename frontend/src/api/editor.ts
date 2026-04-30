import { api } from '@/api/client'

export type EditorOpenMethod = 'external' | 'embedded' | 'clipboard'

export interface EditorStatus {
  available: boolean
  url: string | null
  version: string | null
  control_available: boolean
}

export interface EditorOpenResponse {
  opened: boolean
  method: EditorOpenMethod
  url: string | null
  path: string
  message: string | null
}

type Toast = {
  add: (message: {
    severity: 'success' | 'info' | 'error' | 'warn'
    summary: string
    detail?: string
    life?: number
  }) => void
}

export async function getEditorStatus(): Promise<EditorStatus> {
  const { data } = await api.get<EditorStatus>('/api/v1/editor/status')
  return data
}

export async function openEditorPath(path: string): Promise<EditorOpenResponse> {
  const { data } = await api.post<EditorOpenResponse>('/api/v1/editor/open', { path })
  return data
}

export async function openPathWithEditor(path: string, toast?: Toast | null): Promise<EditorOpenResponse> {
  const response = await openEditorPath(path)
  await handleEditorOpenResponse(response, toast)
  return response
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
    window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
      detail: { url: response.url, path: response.path },
    }))
    return
  }
  await navigator.clipboard?.writeText(response.path)
  toast?.add({
    severity: 'info',
    summary: response.message ?? 'Path copied - open in your local editor.',
    life: 3000,
  })
}
