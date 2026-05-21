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

type WorkflowInfoWithTreeFields = WorkflowInfo & {
  id?: string | null
  folder?: string
  workspace_path?: string | null
  output_path?: string | null
}

type WorkflowFolderResponse = {
  path: string
  display_name: string
  folders: WorkflowFolderResponse[]
  workflows: WorkflowInfoWithTreeFields[]
}

export type WorkflowFolder = {
  id: string
  name: string
  parentId: string | null
}

export type WorkflowTreeWorkflowNode = {
  type: 'workflow'
  workflow: WorkflowInfo
  folderId: string | null
  depth: number
}

export type WorkflowTreeFolderNode = {
  type: 'folder'
  id: string
  name: string
  parentId: string | null
  depth: number
  children: WorkflowTreeNode[]
}

export type WorkflowTreeNode = WorkflowTreeFolderNode | WorkflowTreeWorkflowNode

export class WorkflowConflictError extends Error {
  suggestedName?: string

  constructor(message: string, suggestedName?: string) {
    super(message)
    this.name = 'WorkflowConflictError'
    this.suggestedName = suggestedName
  }
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

function workflowFolderPath(workflow: WorkflowInfo): string | null {
  const folder = (workflow as WorkflowInfoWithTreeFields).folder
  return folder ? folder : null
}

function workflowId(workflow: WorkflowInfo): string {
  return (workflow as WorkflowInfoWithTreeFields).id || workflow.name
}

function childFolderPath(parentId: string | null, name: string): string {
  const trimmed = name.trim().replace(/^\/+|\/+$/g, '')
  return parentId ? `${parentId}/${trimmed}` : trimmed
}

function parentFolderPath(path: string): string | null {
  const index = path.lastIndexOf('/')
  return index === -1 ? null : path.slice(0, index)
}

function workflowUrl(id: string): string {
  return id.split('/').map(encodeURIComponent).join('/')
}

export const useWorkflowStore = defineStore('workflow', () => {
  const workflows = ref<WorkflowInfo[]>([])
  const workflowFolders = ref<WorkflowFolder[]>([])
  const workflowFolderIds = ref<Record<string, string | null>>({})
  const workflowOrder = ref<string[]>([])
  const current = ref<WorkflowInfo | null>(null)
  const missingPackages = ref<MissingPackage[]>([])
  const missingTools = ref<MissingTool[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const uiStore = useUIStore()
  const autoSave = useAutoSave()

  const currentName = computed(() => current.value ? workflowId(current.value) : null)
  const hasWorkflow = computed(() => current.value !== null)
  const workflowByName = computed(() => new Map(
    workflows.value.map((workflow) => [workflowId(workflow), workflow]),
  ))
  const validFolderIds = computed(() => new Set(
    workflowFolders.value.map((folder) => folder.id),
  ))

  function folderExists(folderId: string | null): boolean {
    return folderId === null || validFolderIds.value.has(folderId)
  }

  function applyWorkflowList(items: WorkflowInfo[]): void {
    workflows.value = items
    workflowFolderIds.value = Object.fromEntries(
      items.map((workflow) => [workflowId(workflow), workflowFolderPath(workflow)]),
    )
    sanitizeWorkflowTreeState()
  }

  function applyWorkflowTree(root: WorkflowFolderResponse): void {
    const folders: WorkflowFolder[] = []
    const items: WorkflowInfo[] = []
    const order: string[] = []
    const folderIds: Record<string, string | null> = {}

    function visit(folder: WorkflowFolderResponse): void {
      if (folder.path) {
        folders.push({
          id: folder.path,
          name: folder.display_name,
          parentId: parentFolderPath(folder.path),
        })
      }
      for (const workflow of folder.workflows) {
        items.push(workflow)
        const id = workflowId(workflow)
        order.push(id)
        folderIds[id] = workflow.folder || folder.path || null
      }
      for (const child of folder.folders) {
        visit(child)
      }
    }

    visit(root)
    workflowFolders.value = folders
    workflows.value = items
    workflowOrder.value = order
    workflowFolderIds.value = folderIds
    sanitizeWorkflowTreeState()
  }

  function sanitizeWorkflowTreeState(): void {
    const workflowNames = new Set(workflows.value.map((workflow) => workflowId(workflow)))
    workflowFolderIds.value = Object.fromEntries(
      Object.entries(workflowFolderIds.value)
        .filter(([name]) => workflowNames.has(name))
        .map(([name, folderId]) => [
          name,
          folderExists(folderId) ? folderId : null,
        ]),
    )
    workflowOrder.value = [
      ...workflowOrder.value.filter((name) => workflowNames.has(name)),
      ...workflows.value
        .map((workflow) => workflowId(workflow))
        .filter((name) => !workflowOrder.value.includes(name)),
    ]
  }

  function workflowFolderId(name: string): string | null {
    const folderId = workflowFolderIds.value[name] ?? null
    return folderExists(folderId) ? folderId : null
  }

  function workflowsForFolder(folderId: string | null): WorkflowInfo[] {
    const namesInOrder = workflowOrder.value
      .filter((name) => workflowByName.value.has(name))
    const knownNames = new Set(namesInOrder)
    const fallbackNames = workflows.value
      .map((workflow) => workflowId(workflow))
      .filter((name) => !knownNames.has(name))
    return [...namesInOrder, ...fallbackNames]
      .filter((name) => workflowFolderId(name) === folderId)
      .map((name) => workflowByName.value.get(name))
      .filter((workflow): workflow is WorkflowInfo => workflow !== undefined)
  }

  function foldersForParent(parentId: string | null): WorkflowFolder[] {
    return workflowFolders.value
      .filter((folder) => folder.parentId === parentId)
      .sort((a, b) => a.name.localeCompare(b.name))
  }

  function buildTree(parentId: string | null, depth: number): WorkflowTreeNode[] {
    const folders = foldersForParent(parentId).map((folder): WorkflowTreeFolderNode => ({
      type: 'folder',
      id: folder.id,
      name: folder.name,
      parentId: folder.parentId,
      depth,
      children: buildTree(folder.id, depth + 1),
    }))
    const workflowNodes = workflowsForFolder(parentId).map((workflow): WorkflowTreeWorkflowNode => ({
      type: 'workflow',
      workflow,
      folderId: parentId,
      depth,
    }))
    return [...folders, ...workflowNodes]
  }

  function flattenTree(nodes: WorkflowTreeNode[]): WorkflowInfo[] {
    return nodes.flatMap((node) => (
      node.type === 'workflow' ? [node.workflow] : flattenTree(node.children)
    ))
  }

  const workflowTree = computed<WorkflowTreeNode[]>(() => buildTree(null, 0))
  const flattenedWorkflows = computed<WorkflowInfo[]>(() => flattenTree(workflowTree.value))

  function upsertWorkflow(info: WorkflowInfo, previousName?: string): void {
    const existing = workflows.value.filter((item) => (
      workflowId(item) !== previousName || workflowId(item) === workflowId(info)
    ))
    workflows.value = existing
    const index = workflows.value.findIndex((item) => workflowId(item) === workflowId(info))
    if (index === -1) {
      workflows.value = [...workflows.value, info].sort((a, b) => (
        a.display_name.localeCompare(b.display_name)
      ))
    } else {
      workflows.value[index] = info
    }
    const infoId = workflowId(info)
    if (previousName && previousName !== infoId) {
      const previousFolderId = workflowFolderIds.value[previousName]
      delete workflowFolderIds.value[previousName]
      if (previousFolderId !== undefined) {
        workflowFolderIds.value[infoId] = previousFolderId
      }
      workflowOrder.value = workflowOrder.value.map((name) => (
        name === previousName ? infoId : name
      ))
    }
    sanitizeWorkflowTreeState()
  }

  function setCurrent(info: WorkflowInfo | null): void {
    current.value = info
    uiStore.setActiveWorkflow(info?.display_name ?? null)
  }

  function activateWorkflow(name: string): WorkflowInfo | null {
    const info = workflows.value.find((workflow) => workflowId(workflow) === name) ?? null
    if (info) {
      setCurrent(info)
    }
    return info
  }

  async function fetchWorkflows(): Promise<WorkflowInfo[]> {
    isLoading.value = true
    try {
      const { data } = await api.get<WorkflowInfo[]>('/api/v1/workflows')
      applyWorkflowList(data)
      error.value = null
      return data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : String(err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchWorkflowTree(): Promise<WorkflowTreeNode[]> {
    isLoading.value = true
    try {
      const { data } = await api.get<WorkflowFolderResponse>('/api/v1/workflows/tree')
      applyWorkflowTree(data)
      error.value = null
      return workflowTree.value
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
      await autoSave.setLastOpenedWorkflow(workflowId(data))
      return data
    } catch (err: unknown) {
      const conflict = conflictFromError(err)
      if (conflict) throw conflict
      throw err
    }
  }

  async function loadWorkflow(name: string): Promise<GraphState> {
    const { data } = await api.get<WorkflowFile>(`/api/v1/workflows/${workflowUrl(name)}`)
    upsertWorkflow(data.info)
    setCurrent(data.info)
    missingPackages.value = data.missing_packages ?? []
    missingTools.value = data.missing_tools ?? []
    uiStore.markClean()
    await autoSave.setLastOpenedWorkflow(workflowId(data.info))
    return data.graph
  }

  async function saveWorkflow(graph: GraphState): Promise<WorkflowInfo> {
    if (current.value === null) {
      throw new Error('No active workflow to save')
    }
    const { data } = await api.put<WorkflowInfo>(
      `/api/v1/workflows/${workflowUrl(currentName.value || workflowId(current.value))}`,
      { graph },
    )
    upsertWorkflow(data)
    setCurrent(data)
    uiStore.markClean()
    await autoSave.clearAutoSave(workflowId(data))
    await autoSave.setLastOpenedWorkflow(workflowId(data))
    return data
  }

  async function deleteWorkflow(name: string): Promise<void> {
    await api.delete(`/api/v1/workflows/${workflowUrl(name)}`)
    workflows.value = workflows.value.filter((item) => workflowId(item) !== name)
    delete workflowFolderIds.value[name]
    workflowOrder.value = workflowOrder.value.filter((item) => item !== name)
    await autoSave.clearAutoSave(name)
    if (currentName.value === name) {
      setCurrent(null)
      missingPackages.value = []
      missingTools.value = []
      uiStore.markClean()
      await autoSave.setLastOpenedWorkflow(null)
    }
  }

  async function exportWorkflow(name: string): Promise<void> {
    const response = await api.post<Blob>(
      `/api/v1/workflows/${workflowUrl(name)}/export`,
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
        `/api/v1/workflows/${workflowUrl(name)}`,
        patch,
      )
      upsertWorkflow(data, patch.action === 'update' ? name : undefined)
      setCurrent(data)
      const dataId = workflowId(data)
      if (patch.action === 'update' && dataId !== name) {
        await autoSave.renameWorkflow(name, dataId)
      }
      await autoSave.setLastOpenedWorkflow(dataId)
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
      `/api/v1/workflows/${workflowUrl(currentName.value ?? '')}/rebind-versions`,
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

  async function createWorkflowFolder(
    name: string,
    parentId: string | null = null,
  ): Promise<WorkflowFolder> {
    const trimmed = name.trim()
    if (!trimmed) {
      throw new Error('Folder name is required')
    }
    if (!folderExists(parentId)) {
      throw new Error('Parent folder does not exist')
    }
    const path = childFolderPath(parentId, trimmed)
    const { data } = await api.post<WorkflowFolderResponse>('/api/v1/workflows/folders', {
      path,
    })
    const folder: WorkflowFolder = {
      id: data.path,
      name: data.display_name,
      parentId: parentFolderPath(data.path),
    }
    workflowFolders.value = [...workflowFolders.value, folder]
    return folder
  }

  async function renameWorkflowFolder(id: string, name: string): Promise<void> {
    const trimmed = name.trim()
    if (!trimmed) {
      throw new Error('Folder name is required')
    }
    const index = workflowFolders.value.findIndex((folder) => folder.id === id)
    if (index === -1) {
      throw new Error('Folder does not exist')
    }
    const newPath = childFolderPath(workflowFolders.value[index].parentId, trimmed)
    const { data } = await api.patch<WorkflowFolderResponse>(
      `/api/v1/workflows/folders/${workflowUrl(id)}`,
      { new_path: newPath },
    )
    const nextId = data.path
    workflowFolders.value[index] = {
      ...workflowFolders.value[index],
      id: nextId,
      name: data.display_name,
      parentId: parentFolderPath(nextId),
    }
    workflowFolderIds.value = Object.fromEntries(
      Object.entries(workflowFolderIds.value).map(([workflowName, folderId]) => [
        workflowName,
        folderId === id || folderId?.startsWith(`${id}/`)
          ? `${nextId}${folderId.slice(id.length)}`
          : folderId,
      ]),
    )
  }

  async function deleteWorkflowFolder(id: string): Promise<void> {
    const folder = workflowFolders.value.find((item) => item.id === id)
    if (!folder) return
    await api.delete(`/api/v1/workflows/folders/${workflowUrl(id)}`)
    const childIds = new Set<string>([id])
    let changed = true
    while (changed) {
      changed = false
      for (const item of workflowFolders.value) {
        if (item.parentId && childIds.has(item.parentId) && !childIds.has(item.id)) {
          childIds.add(item.id)
          changed = true
        }
      }
    }
    workflowFolders.value = workflowFolders.value.filter((item) => !childIds.has(item.id))
    workflowFolderIds.value = Object.fromEntries(
      Object.entries(workflowFolderIds.value).map(([name, folderId]) => [
        name,
        folderId && childIds.has(folderId) ? folder.parentId : folderId,
      ]),
    )
  }

  async function moveWorkflowToFolder(
    name: string,
    folderId: string | null,
    targetIndex?: number,
  ): Promise<void> {
    if (!workflowByName.value.has(name)) {
      throw new Error('Workflow does not exist')
    }
    if (!folderExists(folderId)) {
      throw new Error('Folder does not exist')
    }
    const previousFolderId = workflowFolderId(name)
    if (previousFolderId !== folderId) {
      const { data } = await api.patch<WorkflowInfo>(
        `/api/v1/workflows/${workflowUrl(name)}`,
        { action: 'update', folder: folderId ?? '' },
      )
      upsertWorkflow(data, name)
    }
    workflowFolderIds.value = {
      ...workflowFolderIds.value,
      [name]: folderId,
    }
    const currentOrder = workflowOrder.value
      .filter((item) => item !== name && workflowByName.value.has(item))
    const peers = currentOrder.filter((item) => workflowFolderId(item) === folderId)
    if (targetIndex === undefined || targetIndex >= peers.length) {
      const lastPeer = peers[peers.length - 1]
      const insertAt = lastPeer ? currentOrder.indexOf(lastPeer) + 1 : currentOrder.length
      currentOrder.splice(insertAt, 0, name)
    } else {
      const beforeName = peers[Math.max(0, targetIndex)]
      const insertAt = beforeName ? currentOrder.indexOf(beforeName) : currentOrder.length
      currentOrder.splice(insertAt, 0, name)
    }
    workflowOrder.value = currentOrder
    sanitizeWorkflowTreeState()
  }

  async function moveWorkflowBefore(name: string, beforeName: string): Promise<void> {
    if (name === beforeName) return
    if (!workflowByName.value.has(name) || !workflowByName.value.has(beforeName)) {
      throw new Error('Workflow does not exist')
    }
    const folderId = workflowFolderId(beforeName)
    const previousFolderId = workflowFolderId(name)
    if (previousFolderId !== folderId) {
      const { data } = await api.patch<WorkflowInfo>(
        `/api/v1/workflows/${workflowUrl(name)}`,
        { action: 'update', folder: folderId ?? '' },
      )
      upsertWorkflow(data, name)
    }
    workflowFolderIds.value = {
      ...workflowFolderIds.value,
      [name]: folderId,
    }
    const currentOrder = [
      ...workflowOrder.value.filter((item) => workflowByName.value.has(item)),
      ...workflows.value
        .map((workflow) => workflowId(workflow))
        .filter((item) => !workflowOrder.value.includes(item)),
    ].filter((item) => item !== name)
    const insertAt = currentOrder.indexOf(beforeName)
    currentOrder.splice(insertAt === -1 ? currentOrder.length : insertAt, 0, name)
    workflowOrder.value = currentOrder
    sanitizeWorkflowTreeState()
  }

  return {
    workflows,
    workflowFolders,
    workflowFolderIds,
    workflowOrder,
    workflowTree,
    flattenedWorkflows,
    current,
    currentName,
    hasWorkflow,
    missingPackages,
    missingTools,
    isLoading,
    error,
    activateWorkflow,
    fetchWorkflows,
    fetchWorkflowTree,
    createWorkflow,
    loadWorkflow,
    saveWorkflow,
    deleteWorkflow,
    exportWorkflow,
    importWorkflow,
    patchWorkflow,
    rebindVersions,
    createWorkflowFolder,
    renameWorkflowFolder,
    deleteWorkflowFolder,
    moveWorkflowToFolder,
    moveWorkflowBefore,
    markDirty,
    markClean,
  }
})
