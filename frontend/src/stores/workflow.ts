import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { AxiosError } from 'axios'
import { api } from '@/api/client'
import { useAutoSave } from '@/composables/useAutoSave'
import { useUIStore } from '@/stores/ui'
import {
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'
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

export type WorkflowFolderDeletePolicy = 'empty' | 'delete_children' | 'move_children_up'

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

export interface WorkflowSaveTarget {
  canvasId: CanvasId
  workflowName: string
}

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

function folderLeafName(path: string): string {
  const index = path.lastIndexOf('/')
  return index === -1 ? path : path.slice(index + 1)
}

function workflowFullId(workflow: WorkflowInfo): string {
  return workflowId(workflow)
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

  function workflowIdsInFolderPrefix(folderId: string): string[] {
    return workflows.value
      .map((workflow) => workflowId(workflow))
      .filter((id) => id === folderId || id.startsWith(`${folderId}/`))
  }

  function remapWorkflowIdPrefix(id: string, oldPrefix: string, newPrefix: string | null): string {
    if (id === oldPrefix) return newPrefix ?? ''
    if (!id.startsWith(`${oldPrefix}/`)) return id
    const suffix = id.slice(oldPrefix.length + 1)
    return newPrefix ? `${newPrefix}/${suffix}` : suffix
  }

  async function renameAutoSavesForFolderMove(
    oldPrefix: string,
    newPrefix: string | null,
  ): Promise<void> {
    const moves = workflowIdsInFolderPrefix(oldPrefix)
      .map((id) => [id, remapWorkflowIdPrefix(id, oldPrefix, newPrefix)] as const)
      .filter(([oldId, newId]) => oldId !== newId && newId.length > 0)
    for (const [oldId, newId] of moves) {
      await autoSave.renameWorkflow(oldId, newId)
    }
  }

  async function clearAutoSavesForFolder(folderId: string): Promise<void> {
    for (const id of workflowIdsInFolderPrefix(folderId)) {
      await autoSave.clearAutoSave(id)
    }
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
    return [...folders, ...workflowNodes].sort((a, b) => {
      const aLabel = a.type === 'folder' ? a.name : a.workflow.display_name
      const bLabel = b.type === 'folder' ? b.name : b.workflow.display_name
      return aLabel.localeCompare(bLabel)
    })
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

  function setCurrent(info: WorkflowInfo | null, canvasId?: CanvasId): void {
    current.value = info
    const id = info === null ? null : workflowId(info)
    if (canvasId !== undefined) {
      uiStore.setCanvasWorkflow(canvasId, id, info?.display_name ?? null)
    } else if (canvasSessionRegistry.sessionCount.value === 0) {
      uiStore.setActiveWorkflowIdentity(id, info?.display_name ?? null)
    }
  }

  function markPresentationClean(canvasId?: CanvasId): void {
    if (canvasId !== undefined) {
      uiStore.markCanvasClean(canvasId)
    } else if (canvasSessionRegistry.sessionCount.value === 0) {
      uiStore.markClean()
    }
  }

  function activateWorkflow(name: string, canvasId?: CanvasId): WorkflowInfo | null {
    const info = workflows.value.find((workflow) => workflowId(workflow) === name) ?? null
    if (info) {
      setCurrent(info, canvasId)
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

  async function createWorkflow(
    body: WorkflowCreate,
    canvasId?: CanvasId,
  ): Promise<WorkflowInfo> {
    try {
      const { data } = await api.post<WorkflowInfo>('/api/v1/workflows', body)
      upsertWorkflow(data)
      setCurrent(data, canvasId)
      missingPackages.value = []
      missingTools.value = []
      markPresentationClean(canvasId)
      await autoSave.setLastOpenedWorkflow(workflowId(data))
      return data
    } catch (err: unknown) {
      const conflict = conflictFromError(err)
      if (conflict) throw conflict
      throw err
    }
  }

  async function loadWorkflow(name: string, canvasId?: CanvasId): Promise<GraphState> {
    const { data } = await api.get<WorkflowFile>(`/api/v1/workflows/${workflowUrl(name)}`)
    upsertWorkflow(data.info)
    setCurrent(data.info, canvasId)
    missingPackages.value = data.missing_packages ?? []
    missingTools.value = data.missing_tools ?? []
    markPresentationClean(canvasId)
    await autoSave.setLastOpenedWorkflow(workflowId(data.info))
    return data.graph
  }

  async function saveWorkflow(
    graph: GraphState,
    target?: WorkflowSaveTarget,
  ): Promise<WorkflowInfo> {
    const targetWorkflowName = target?.workflowName
      ?? currentName.value
      ?? (current.value === null ? null : workflowId(current.value))
    if (targetWorkflowName === null) {
      throw new Error('No active workflow to save')
    }
    const { data } = await api.put<WorkflowInfo>(
      `/api/v1/workflows/${workflowUrl(targetWorkflowName)}`,
      { graph },
    )
    upsertWorkflow(data)
    await autoSave.clearAutoSave(workflowId(data))
    if (target === undefined) {
      setCurrent(data)
      markPresentationClean()
      await autoSave.setLastOpenedWorkflow(workflowId(data))
      return data
    }

    if (uiStore.canvasWorkflowId(target.canvasId) !== targetWorkflowName) {
      return data
    }
    uiStore.setCanvasWorkflow(
      target.canvasId,
      workflowId(data),
      data.display_name,
    )
    uiStore.markCanvasClean(target.canvasId)
    if (
      canvasSessionRegistry.activeCanvasId.value === target.canvasId
      && currentName.value === targetWorkflowName
    ) {
      current.value = data
      await autoSave.setLastOpenedWorkflow(workflowId(data))
    }
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
      markPresentationClean()
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

  function markDirty(canvasId?: CanvasId): void {
    if (canvasId !== undefined) {
      uiStore.markCanvasDirty(canvasId)
    } else if (canvasSessionRegistry.sessionCount.value === 0) {
      uiStore.markDirty()
    }
  }

  function markClean(canvasId?: CanvasId): void {
    markPresentationClean(canvasId)
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
    const previousCurrent = currentName.value
    const nextCurrent = previousCurrent ? remapWorkflowIdPrefix(previousCurrent, id, nextId) : null
    await renameAutoSavesForFolderMove(id, nextId)
    await fetchWorkflowTree()
    if (nextCurrent) {
      activateWorkflow(nextCurrent)
    }
  }

  async function deleteWorkflowFolder(
    id: string,
    policy: WorkflowFolderDeletePolicy = 'empty',
  ): Promise<void> {
    const folder = workflowFolders.value.find((item) => item.id === id)
    if (!folder) return
    await api.delete(`/api/v1/workflows/folders/${workflowUrl(id)}`, {
      data: { policy },
    })
    if (policy === 'delete_children') {
      await clearAutoSavesForFolder(id)
      if (currentName.value && remapWorkflowIdPrefix(currentName.value, id, null) !== currentName.value) {
        setCurrent(null)
        await autoSave.setLastOpenedWorkflow(null)
      }
      await fetchWorkflowTree()
      return
    }
    const previousCurrent = currentName.value
    const nextCurrent = previousCurrent
      ? remapWorkflowIdPrefix(previousCurrent, id, folder.parentId)
      : null
    await renameAutoSavesForFolderMove(id, folder.parentId)
    await fetchWorkflowTree()
    if (nextCurrent) {
      activateWorkflow(nextCurrent)
    }
  }

  async function moveWorkflowFolder(
    id: string,
    targetParentId: string | null,
  ): Promise<void> {
    const folder = workflowFolders.value.find((item) => item.id === id)
    if (!folder) {
      throw new Error('Folder does not exist')
    }
    if (!folderExists(targetParentId)) {
      throw new Error('Target folder does not exist')
    }
    if (targetParentId === id || targetParentId?.startsWith(`${id}/`)) {
      throw new Error('Cannot move a folder into itself')
    }
    const nextPath = childFolderPath(targetParentId, folderLeafName(id))
    const { data } = await api.patch<WorkflowFolderResponse>(
      `/api/v1/workflows/folders/${workflowUrl(id)}`,
      { new_path: nextPath },
    )
    const nextId = data.path
    const previousCurrent = currentName.value
    const nextCurrent = previousCurrent ? remapWorkflowIdPrefix(previousCurrent, id, nextId) : null
    await renameAutoSavesForFolderMove(id, nextId)
    await fetchWorkflowTree()
    if (nextCurrent) {
      activateWorkflow(nextCurrent)
    }
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
    const previousName = name
    const wasCurrent = currentName.value === previousName
    if (previousFolderId !== folderId) {
      const { data } = await api.patch<WorkflowInfo>(
        `/api/v1/workflows/${workflowUrl(name)}`,
        { action: 'update', folder: folderId ?? '' },
      )
      upsertWorkflow(data, name)
      name = workflowFullId(data)
      if (name !== previousName) {
        await autoSave.renameWorkflow(previousName, name)
      }
      if (wasCurrent) {
        setCurrent(data)
        await autoSave.setLastOpenedWorkflow(name)
      }
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
    const previousName = name
    const wasCurrent = currentName.value === previousName
    if (previousFolderId !== folderId) {
      const { data } = await api.patch<WorkflowInfo>(
        `/api/v1/workflows/${workflowUrl(name)}`,
        { action: 'update', folder: folderId ?? '' },
      )
      upsertWorkflow(data, name)
      name = workflowFullId(data)
      if (name !== previousName) {
        await autoSave.renameWorkflow(previousName, name)
      }
      if (wasCurrent) {
        setCurrent(data)
        await autoSave.setLastOpenedWorkflow(name)
      }
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
    moveWorkflowFolder,
    moveWorkflowToFolder,
    moveWorkflowBefore,
    markDirty,
    markClean,
  }
})
