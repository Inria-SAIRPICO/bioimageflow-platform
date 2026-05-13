import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { AxiosError } from 'axios'
import { api } from '@/api/client'
import { useAutoSave } from '@/composables/useAutoSave'
import { useUIStore } from '@/stores/ui'
import type {
  GraphState,
  MissingPackage,
  MissingTool,
  WorkflowCreate,
  WorkflowFile,
  WorkflowInfo,
  WorkflowImportResponse,
  WorkflowUpdate,
} from '@/api/types'

export class WorkflowConflictError extends Error {
  suggestedName?: string

  constructor(message: string, suggestedName?: string) {
    super(message)
    this.name = 'WorkflowConflictError'
    this.suggestedName = suggestedName
  }
}

export interface WorkflowSaveDraftIdentity {
  draft_id?: string | null
  revision?: number | null
}

function conflictFromError(err: unknown): WorkflowConflictError | null {
  if (!(err instanceof AxiosError) || err.response?.status !== 409) return null
  const data = err.response.data as { detail?: string; suggested_name?: string }
  return new WorkflowConflictError(
    data.detail ?? 'Workflow already exists',
    data.suggested_name,
  )
}

function filenameFromDisposition(disposition: unknown, fallback: string): string {
  if (typeof disposition !== 'string') return fallback
  const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1].replace(/"/g, ''))
  const match = disposition.match(/filename="?([^";]+)"?/i)
  return match?.[1] ?? fallback
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}

export const useWorkflowStore = defineStore('workflow', () => {
  const workflows = ref<WorkflowInfo[]>([])
  const current = ref<WorkflowInfo | null>(null)
  const missingPackages = ref<MissingPackage[]>([])
  const missingTools = ref<MissingTool[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const uiStore = useUIStore()
  const autoSave = useAutoSave()

  const currentName = computed(() => current.value?.name ?? null)
  const hasWorkflow = computed(() => current.value !== null)

  function upsertWorkflow(info: WorkflowInfo, previousName?: string): void {
    const existing = workflows.value.filter((item) => (
      item.name !== previousName || item.name === info.name
    ))
    workflows.value = existing
    const index = workflows.value.findIndex((item) => item.name === info.name)
    if (index === -1) {
      workflows.value = [...workflows.value, info].sort((a, b) => (
        a.display_name.localeCompare(b.display_name)
      ))
    } else {
      workflows.value[index] = info
    }
  }

  function setCurrent(info: WorkflowInfo | null): void {
    current.value = info
    uiStore.setActiveWorkflow(info?.display_name ?? null)
  }

  function activateWorkflow(name: string): WorkflowInfo | null {
    const info = workflows.value.find((workflow) => workflow.name === name) ?? null
    if (info) {
      setCurrent(info)
    }
    return info
  }

  async function fetchWorkflows(): Promise<WorkflowInfo[]> {
    isLoading.value = true
    try {
      const { data } = await api.get<WorkflowInfo[]>('/api/v1/workflows')
      workflows.value = data
      error.value = null
      return data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : String(err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function createWorkflow(body: WorkflowCreate): Promise<WorkflowInfo> {
    try {
      const { data } = await api.post<WorkflowInfo>('/api/v1/workflows', body)
      upsertWorkflow(data)
      setCurrent(data)
      missingPackages.value = []
      missingTools.value = []
      uiStore.markClean()
      await autoSave.setLastOpenedWorkflow(data.name)
      return data
    } catch (err: unknown) {
      const conflict = conflictFromError(err)
      if (conflict) throw conflict
      throw err
    }
  }

  async function loadWorkflow(name: string): Promise<GraphState> {
    const { data } = await api.get<WorkflowFile>(`/api/v1/workflows/${name}`)
    upsertWorkflow(data.info)
    setCurrent(data.info)
    missingPackages.value = data.missing_packages ?? []
    missingTools.value = data.missing_tools ?? []
    uiStore.markClean()
    await autoSave.setLastOpenedWorkflow(data.info.name)
    return data.graph
  }

  async function saveWorkflow(
    graph: GraphState,
    draft?: WorkflowSaveDraftIdentity,
  ): Promise<WorkflowInfo> {
    if (current.value === null) {
      throw new Error('No active workflow to save')
    }
    const body: {
      graph: GraphState
      draft_id?: string
      revision?: number
    } = { graph }
    if (draft?.draft_id) {
      body.draft_id = draft.draft_id
      if (typeof draft.revision === 'number') {
        body.revision = draft.revision
      }
    }
    const { data } = await api.put<WorkflowInfo>(
      `/api/v1/workflows/${current.value.name}`,
      body,
    )
    upsertWorkflow(data)
    setCurrent(data)
    uiStore.markClean()
    await autoSave.clearAutoSave(data.name)
    await autoSave.setLastOpenedWorkflow(data.name)
    return data
  }

  async function deleteWorkflow(name: string): Promise<void> {
    await api.delete(`/api/v1/workflows/${name}`)
    workflows.value = workflows.value.filter((item) => item.name !== name)
    await autoSave.clearAutoSave(name)
    if (current.value?.name === name) {
      setCurrent(null)
      missingPackages.value = []
      missingTools.value = []
      uiStore.markClean()
      await autoSave.setLastOpenedWorkflow(null)
    }
  }

  async function exportWorkflow(name: string): Promise<void> {
    const response = await api.post<Blob>(
      `/api/v1/workflows/${name}/export`,
      undefined,
      { responseType: 'blob' },
    )
    const filename = filenameFromDisposition(
      response.headers?.['content-disposition'],
      `${name}.bioimageflow.zip`,
    )
    downloadBlob(response.data, filename)
  }

  async function importWorkflow(
    file: File,
    options: { nameOverride?: string } = {},
  ): Promise<WorkflowImportResponse> {
    const body = new FormData()
    body.append('file', file)
    if (options.nameOverride) {
      body.append('name_override', options.nameOverride)
    }
    try {
      const { data } = await api.post<WorkflowImportResponse>(
        '/api/v1/workflows/import',
        body,
      )
      upsertWorkflow(data.info)
      missingPackages.value = data.missing_packages ?? []
      missingTools.value = data.missing_tools ?? []
      return data
    } catch (err: unknown) {
      const conflict = conflictFromError(err)
      if (conflict) throw conflict
      throw err
    }
  }

  async function patchWorkflow(
    name: string,
    patch: WorkflowUpdate,
  ): Promise<WorkflowInfo> {
    try {
      const { data } = await api.patch<WorkflowInfo>(
        `/api/v1/workflows/${name}`,
        patch,
      )
      upsertWorkflow(data, patch.action === 'update' ? name : undefined)
      setCurrent(data)
      if (patch.action === 'update' && data.name !== name) {
        await autoSave.renameWorkflow(name, data.name)
      }
      await autoSave.setLastOpenedWorkflow(data.name)
      return data
    } catch (err: unknown) {
      const conflict = conflictFromError(err)
      if (conflict) throw conflict
      throw err
    }
  }

  async function rebindVersions(): Promise<GraphState> {
    if (current.value === null) {
      throw new Error('No active workflow to rebind')
    }
    const { data } = await api.post<WorkflowFile>(
      `/api/v1/workflows/${current.value.name}/rebind-versions`,
    )
    upsertWorkflow(data.info)
    setCurrent(data.info)
    missingPackages.value = data.missing_packages ?? []
    missingTools.value = data.missing_tools ?? []
    return data.graph
  }

  function markDirty(): void {
    uiStore.markDirty()
  }

  function markClean(): void {
    uiStore.markClean()
  }

  return {
    workflows,
    current,
    currentName,
    hasWorkflow,
    missingPackages,
    missingTools,
    isLoading,
    error,
    activateWorkflow,
    fetchWorkflows,
    createWorkflow,
    loadWorkflow,
    saveWorkflow,
    deleteWorkflow,
    exportWorkflow,
    importWorkflow,
    patchWorkflow,
    rebindVersions,
    markDirty,
    markClean,
  }
})
