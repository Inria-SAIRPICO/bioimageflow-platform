import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { AxiosError } from 'axios'
import { api } from '@/api/client'
import { useAutoSave } from '@/composables/useAutoSave'
import { useUIStore } from '@/stores/ui'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import {
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'
import { clearRecoveryPersistenceKeyStrict } from '@/sessions/recoveryPersistenceCoordinator'
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
  identity_generation?: number
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

export class WorkflowIdentityChangedError extends Error {
  constructor(workflowName: string) {
    super(`Workflow '${workflowName}' changed identity while it was being opened.`)
    this.name = 'WorkflowIdentityChangedError'
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
  const workflowIdentityGenerations = new Map<string, number>()
  const workflowServerIdentityGenerations = new Map<string, number>()
  const workflowDeletionsInFlight = new Set<string>()
  const workflowRemovalPromises = new Map<string, Promise<void>>()
  const workflowPresentationResetPromises = new Map<string, Promise<void>>()
  let workflowCollectionGeneration = 0

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

  function workflowIdentityGeneration(name: string): number {
    return workflowIdentityGenerations.get(name) ?? 0
  }

  function workflowServerIdentityGeneration(name: string): number | null {
    return workflowServerIdentityGenerations.get(name) ?? null
  }

  function observeWorkflowServerIdentityGeneration(
    name: string,
    generation: number,
    options: { structuralEvent?: boolean } = {},
  ): boolean {
    if (!Number.isInteger(generation) || generation < 0) return false
    const known = workflowServerIdentityGeneration(name)
    if (known !== null && generation < known) return false
    if (known === null || generation > known) {
      workflowServerIdentityGenerations.set(name, generation)
      if (options.structuralEvent) workflowCollectionGeneration += 1
    }
    return true
  }

  function noteWorkflowStructuralEvent(): void {
    workflowCollectionGeneration += 1
  }

  function acceptWorkflowInfoGeneration(info: WorkflowInfo): boolean {
    const name = workflowId(info)
    const generation = (info as WorkflowInfoWithTreeFields).identity_generation
    if (generation === undefined) return true
    return observeWorkflowServerIdentityGeneration(name, generation)
  }

  function invalidateWorkflowIdentity(name: string): number {
    const generation = workflowIdentityGeneration(name) + 1
    workflowIdentityGenerations.set(name, generation)
    workflowCollectionGeneration += 1
    return generation
  }

  function isWorkflowDeletionInFlight(name: string): boolean {
    return workflowDeletionsInFlight.has(name)
  }

  function isWorkflowIdentityCurrent(name: string, generation: number): boolean {
    return !isWorkflowDeletionInFlight(name)
      && workflowIdentityGeneration(name) === generation
  }

  function assertWorkflowIdentityCurrent(name: string, generation: number): void {
    if (!isWorkflowIdentityCurrent(name, generation)) {
      throw new WorkflowIdentityChangedError(name)
    }
  }

  function captureWorkflowIdentity(name: string): number {
    const generation = workflowIdentityGeneration(name)
    assertWorkflowIdentityCurrent(name, generation)
    return generation
  }

  function folderExists(folderId: string | null): boolean {
    return folderId === null || validFolderIds.value.has(folderId)
  }

  function applyWorkflowList(items: WorkflowInfo[]): void {
    const acceptedItems = items.filter(acceptWorkflowInfoGeneration)
    workflows.value = acceptedItems
    workflowFolderIds.value = Object.fromEntries(
      acceptedItems.map((workflow) => [workflowId(workflow), workflowFolderPath(workflow)]),
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
        if (!acceptWorkflowInfoGeneration(workflow)) continue
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

  function assertWorkflowIdentitiesUnmounted(
    workflowIds: Iterable<string>,
    closingCanvasId?: CanvasId,
  ): void {
    const affected = [...new Set(workflowIds)].filter((id) => (
      uiStore.canvasIdsForWorkflow(id).some((canvasId) => (
        canvasId !== closingCanvasId && canvasSessionRegistry.get(canvasId) !== null
      ))
    ))
    if (affected.length === 0) return
    const names = affected.map((id) => `'${id}'`).join(', ')
    throw new Error(
      `Close the affected workflow and sub-workflow tabs before renaming, moving, or deleting ${names}.`,
    )
  }

  function workflowUpdateIdentity(name: string, patch: WorkflowUpdate): string | null {
    if (patch.action !== 'update') return null
    if (patch.new_id !== null && patch.new_id !== undefined) return patch.new_id
    const currentFolder = parentFolderPath(name)
    if (patch.new_name !== null && patch.new_name !== undefined) {
      const targetFolder = patch.folder !== null && patch.folder !== undefined
        ? patch.folder
        : currentFolder
      const leaf = folderLeafName(patch.new_name)
      return targetFolder ? `${targetFolder}/${leaf}` : leaf
    }
    if (patch.folder !== null && patch.folder !== undefined) {
      const leaf = folderLeafName(name)
      return patch.folder ? `${patch.folder}/${leaf}` : leaf
    }
    return null
  }

  type WorkflowIdentityCapture = Map<string, number>

  function captureWorkflowIdentities(workflowIds: Iterable<string>): WorkflowIdentityCapture {
    const captured = new Map<string, number>()
    for (const id of new Set(workflowIds)) {
      if (!id) continue
      captured.set(id, captureWorkflowIdentity(id))
    }
    return captured
  }

  function assertWorkflowIdentitiesCurrent(captured: WorkflowIdentityCapture): void {
    for (const [id, generation] of captured) {
      assertWorkflowIdentityCurrent(id, generation)
    }
  }

  function assertWorkflowGenerationValues(captured: WorkflowIdentityCapture): void {
    for (const [id, generation] of captured) {
      if (workflowIdentityGeneration(id) !== generation) {
        throw new WorkflowIdentityChangedError(id)
      }
    }
  }

  function invalidateWorkflowIdentities(workflowIds: Iterable<string>): WorkflowIdentityCapture {
    const generations = new Map<string, number>()
    for (const id of new Set(workflowIds)) {
      if (!id) continue
      generations.set(id, invalidateWorkflowIdentity(id))
    }
    return generations
  }

  function assertWorkflowInfoIdentity(info: WorkflowInfo, expectedId: string): void {
    if (workflowId(info) !== expectedId || !acceptWorkflowInfoGeneration(info)) {
      throw new WorkflowIdentityChangedError(expectedId)
    }
  }

  function workflowPatchDestination(name: string, patch: WorkflowUpdate): string {
    if (patch.action === 'duplicate') return patch.new_name ?? ''
    return workflowUpdateIdentity(name, patch) ?? name
  }

  function importedWorkflowIdentity(file: File, nameOverride?: string): string {
    if (nameOverride) return nameOverride
    for (const suffix of ['.bioimageflow.zip', '.zip']) {
      if (file.name.endsWith(suffix)) return file.name.slice(0, -suffix.length)
    }
    const extensionIndex = file.name.lastIndexOf('.')
    return extensionIndex > 0 ? file.name.slice(0, extensionIndex) : file.name
  }

  function workflowIdentityMovesForFolder(
    workflowIds: Iterable<string>,
    oldPrefix: string,
    newPrefix: string | null,
  ): Array<readonly [string, string]> {
    return [...workflowIds]
      .map((id) => [id, remapWorkflowIdPrefix(id, oldPrefix, newPrefix)] as const)
      .filter(([oldId, newId]) => oldId !== newId && newId.length > 0)
  }

  function forgetRetainedDrafts(workflowIds: Iterable<string>): void {
    const drafts = useWorkflowDraftStore()
    for (const id of workflowIds) drafts.forgetWorkflow(id)
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
    await renameAutoSavesForIdentityMoves(moves)
  }

  async function renameAutoSavesForIdentityMoves(
    moves: Array<readonly [string, string]>,
  ): Promise<void> {
    for (const [oldId, newId] of moves) {
      await autoSave.renameWorkflow(oldId, newId)
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
    if (!acceptWorkflowInfoGeneration(info)) {
      throw new WorkflowIdentityChangedError(workflowId(info))
    }
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
    }
  }

  function markPresentationClean(canvasId?: CanvasId): void {
    if (canvasId !== undefined) {
      uiStore.markCanvasClean(canvasId)
    }
  }

  function activateWorkflow(name: string, canvasId?: CanvasId): WorkflowInfo | null {
    const info = workflows.value.find((workflow) => workflowId(workflow) === name) ?? null
    if (info) {
      setCurrent(info, canvasId)
    }
    return info
  }

  async function fetchWorkflows(attempt = 0): Promise<WorkflowInfo[]> {
    isLoading.value = true
    const collectionGeneration = workflowCollectionGeneration
    try {
      const { data } = await api.get<WorkflowInfo[]>('/api/v1/workflows')
      if (collectionGeneration !== workflowCollectionGeneration) {
        if (attempt === 0) return fetchWorkflows(1)
        throw new Error('Workflow identities changed while refreshing the workflow list.')
      }
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

  async function fetchWorkflowTree(attempt = 0): Promise<WorkflowTreeNode[]> {
    isLoading.value = true
    const collectionGeneration = workflowCollectionGeneration
    try {
      const { data } = await api.get<WorkflowFolderResponse>('/api/v1/workflows/tree')
      if (collectionGeneration !== workflowCollectionGeneration) {
        if (attempt === 0) return fetchWorkflowTree(1)
        throw new Error('Workflow identities changed while refreshing the workflow tree.')
      }
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
    const requestedName = body.name.trim()
    const requestedGeneration = captureWorkflowIdentity(requestedName)
    try {
      const { data } = await api.post<WorkflowInfo>('/api/v1/workflows', body)
      const createdName = workflowId(data)
      assertWorkflowIdentityCurrent(requestedName, requestedGeneration)
      assertWorkflowInfoIdentity(data, requestedName)
      const identityGeneration = invalidateWorkflowIdentity(createdName)
      upsertWorkflow(data)
      setCurrent(data, canvasId)
      missingPackages.value = []
      missingTools.value = []
      markPresentationClean(canvasId)
      await autoSave.setLastOpenedWorkflow(createdName)
      assertWorkflowIdentityCurrent(createdName, identityGeneration)
      return data
    } catch (err: unknown) {
      const conflict = conflictFromError(err)
      if (conflict) throw conflict
      throw err
    }
  }

  async function loadWorkflow(
    name: string,
    canvasId?: CanvasId,
    options: { rememberAsLastOpened?: boolean } = {},
  ): Promise<GraphState> {
    const identityGeneration = captureWorkflowIdentity(name)
    const { data } = await api.get<WorkflowFile>(`/api/v1/workflows/${workflowUrl(name)}`)
    assertWorkflowIdentityCurrent(name, identityGeneration)
    if (workflowId(data.info) !== name) {
      throw new WorkflowIdentityChangedError(name)
    }
    upsertWorkflow(data.info)
    setCurrent(data.info, canvasId)
    missingPackages.value = data.missing_packages ?? []
    missingTools.value = data.missing_tools ?? []
    markPresentationClean(canvasId)
    if (options.rememberAsLastOpened !== false) {
      await autoSave.setLastOpenedWorkflow(name)
    }
    assertWorkflowIdentityCurrent(name, identityGeneration)
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
    const identityGeneration = captureWorkflowIdentity(targetWorkflowName)
    const { data } = await api.put<WorkflowInfo>(
      `/api/v1/workflows/${workflowUrl(targetWorkflowName)}`,
      { graph },
    )
    assertWorkflowIdentityCurrent(targetWorkflowName, identityGeneration)
    if (workflowId(data) !== targetWorkflowName) {
      throw new WorkflowIdentityChangedError(targetWorkflowName)
    }
    upsertWorkflow(data)
    await autoSave.clearAutoSave(workflowId(data))
    assertWorkflowIdentityCurrent(targetWorkflowName, identityGeneration)
    if (target === undefined) {
      setCurrent(data)
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
    if (
      canvasSessionRegistry.activeCanvasId.value === target.canvasId
      && currentName.value === targetWorkflowName
    ) {
      current.value = data
      await autoSave.setLastOpenedWorkflow(workflowId(data))
    }
    return data
  }

  async function deleteWorkflow(
    name: string,
    options: {
      closingCanvasId?: CanvasId
      allowMountedIdentity?: boolean
      expectedIdentityGeneration?: number
      beforeRecoveryCleanup?: () => void | Promise<void>
    } = {},
  ): Promise<void> {
    if (!options.allowMountedIdentity) {
      assertWorkflowIdentitiesUnmounted([name], options.closingCanvasId)
    }
    if (isWorkflowDeletionInFlight(name)) {
      throw new Error(`Workflow '${name}' is already being deleted.`)
    }
    if (
      options.expectedIdentityGeneration !== undefined
      && workflowServerIdentityGeneration(name) !== options.expectedIdentityGeneration
    ) {
      throw new WorkflowIdentityChangedError(name)
    }
    workflowDeletionsInFlight.add(name)
    try {
      const url = `/api/v1/workflows/${workflowUrl(name)}`
      const request = options.expectedIdentityGeneration === undefined
        ? api.delete<{
            deleted: boolean
            identity_generation?: number
          }>(url)
        : api.delete<{
            deleted: boolean
            identity_generation?: number
          }>(url, {
            params: {
              expected_identity_generation: options.expectedIdentityGeneration,
            },
          })
      const { data } = await request
      invalidateWorkflowIdentity(name)
      if (data.identity_generation !== undefined) {
        const accepted = observeWorkflowServerIdentityGeneration(
          name,
          data.identity_generation,
          { structuralEvent: true },
        )
        if (!accepted) throw new WorkflowIdentityChangedError(name)
      }
      await options.beforeRecoveryCleanup?.()
      await forgetDeletedWorkflow(name)
    } finally {
      workflowDeletionsInFlight.delete(name)
    }
  }

  function forgetDeletedWorkflow(name: string): Promise<void> {
    const existing = workflowRemovalPromises.get(name)
    if (existing) return existing

    const ownsDeletionFence = !workflowDeletionsInFlight.has(name)
    if (ownsDeletionFence) workflowDeletionsInFlight.add(name)
    invalidateWorkflowIdentity(name)
    useWorkflowDraftStore().forgetWorkflow(name)
    workflows.value = workflows.value.filter((item) => workflowId(item) !== name)
    delete workflowFolderIds.value[name]
    workflowOrder.value = workflowOrder.value.filter((item) => item !== name)
    const wasCurrent = currentName.value === name
    if (wasCurrent) {
      setCurrent(null)
      missingPackages.value = []
      missingTools.value = []
      markPresentationClean()
    }

    const cleanup = (async () => {
      const cleanupErrors: string[] = []
      try {
        await clearRecoveryPersistenceKeyStrict(
          name,
          () => autoSave.clearAutoSaveStrict(name),
        )
      } catch (cleanupError) {
        cleanupErrors.push(
          cleanupError instanceof Error ? cleanupError.message : String(cleanupError),
        )
      }
      if (wasCurrent) {
        try {
          await autoSave.setLastOpenedWorkflow(null)
        } catch (cleanupError) {
          cleanupErrors.push(
            cleanupError instanceof Error ? cleanupError.message : String(cleanupError),
          )
        }
      }
      if (cleanupErrors.length > 0) {
        const message = `Workflow '${name}' was deleted, but local recovery cleanup failed: ${cleanupErrors.join('; ')}`
        error.value = message
        throw new Error(message)
      }
    })().finally(() => {
      workflowRemovalPromises.delete(name)
      if (ownsDeletionFence) workflowDeletionsInFlight.delete(name)
    })
    workflowRemovalPromises.set(name, cleanup)
    return cleanup
  }

  function resetWorkflowPresentationGeneration(name: string): Promise<void> {
    const existing = workflowPresentationResetPromises.get(name)
    if (existing) return existing

    const ownsDeletionFence = !workflowDeletionsInFlight.has(name)
    if (ownsDeletionFence) workflowDeletionsInFlight.add(name)
    invalidateWorkflowIdentity(name)
    useWorkflowDraftStore().forgetWorkflow(name)
    const wasCurrent = currentName.value === name
    if (wasCurrent) {
      setCurrent(null)
      missingPackages.value = []
      missingTools.value = []
      markPresentationClean()
    }

    const cleanup = (async () => {
      const cleanupErrors: string[] = []
      try {
        await clearRecoveryPersistenceKeyStrict(
          name,
          () => autoSave.clearAutoSaveStrict(name),
        )
      } catch (cleanupError) {
        cleanupErrors.push(
          cleanupError instanceof Error ? cleanupError.message : String(cleanupError),
        )
      }
      if (wasCurrent) {
        try {
          await autoSave.setLastOpenedWorkflow(null)
        } catch (cleanupError) {
          cleanupErrors.push(
            cleanupError instanceof Error ? cleanupError.message : String(cleanupError),
          )
        }
      }
      if (cleanupErrors.length > 0) {
        const message = `Workflow '${name}' changed generation, but local recovery cleanup failed: ${cleanupErrors.join('; ')}`
        error.value = message
        throw new Error(message)
      }
    })().finally(() => {
      workflowPresentationResetPromises.delete(name)
      if (ownsDeletionFence) workflowDeletionsInFlight.delete(name)
    })
    workflowPresentationResetPromises.set(name, cleanup)
    return cleanup
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
    const requestedName = importedWorkflowIdentity(file, options.nameOverride)
    const requestedGeneration = captureWorkflowIdentity(requestedName)
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
      assertWorkflowIdentityCurrent(requestedName, requestedGeneration)
      assertWorkflowInfoIdentity(data.info, requestedName)
      const identityGeneration = invalidateWorkflowIdentity(requestedName)
      upsertWorkflow(data.info)
      missingPackages.value = data.missing_packages ?? []
      missingTools.value = data.missing_tools ?? []
      assertWorkflowIdentityCurrent(requestedName, identityGeneration)
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
    target?: WorkflowSaveTarget,
  ): Promise<WorkflowInfo> {
    const nextIdentity = workflowUpdateIdentity(name, patch)
    if (nextIdentity !== null && nextIdentity !== name) {
      assertWorkflowIdentitiesUnmounted([name])
    }
    const destination = workflowPatchDestination(name, patch)
    const requestIdentities = captureWorkflowIdentities([name, destination])
    try {
      const { data } = await api.patch<WorkflowInfo>(
        `/api/v1/workflows/${workflowUrl(name)}`,
        patch,
      )
      const dataId = workflowId(data)
      assertWorkflowIdentitiesCurrent(requestIdentities)
      assertWorkflowInfoIdentity(data, destination)
      const appliedIdentities = patch.action === 'duplicate'
        ? invalidateWorkflowIdentities([dataId])
        : dataId === name
          ? requestIdentities
          : invalidateWorkflowIdentities([name, dataId])
      if (patch.action === 'update' && dataId !== name) {
        forgetRetainedDrafts([name])
        await autoSave.renameWorkflow(name, dataId)
        assertWorkflowIdentitiesCurrent(appliedIdentities)
      }
      upsertWorkflow(data, patch.action === 'update' ? name : undefined)
      if (target === undefined) {
        if (patch.action === 'update' && currentName.value === name) {
          current.value = data
        }
        return data
      }

      if (uiStore.canvasWorkflowId(target.canvasId) !== target.workflowName) {
        return data
      }
      uiStore.setCanvasWorkflow(target.canvasId, dataId, data.display_name)
      if (
        canvasSessionRegistry.activeCanvasId.value === target.canvasId
        && currentName.value === target.workflowName
      ) {
        current.value = data
        await autoSave.setLastOpenedWorkflow(dataId)
      }
      return data
    } catch (err: unknown) {
      const conflict = conflictFromError(err)
      if (conflict) throw conflict
      throw err
    }
  }

  async function rebindVersions(target?: WorkflowSaveTarget): Promise<GraphState> {
    const targetWorkflowName = target?.workflowName ?? currentName.value
    if (targetWorkflowName === null) {
      throw new Error('No active workflow to rebind')
    }
    const identityGeneration = captureWorkflowIdentity(targetWorkflowName)
    const { data } = await api.post<WorkflowFile>(
      `/api/v1/workflows/${workflowUrl(targetWorkflowName)}/rebind-versions`,
    )
    assertWorkflowIdentityCurrent(targetWorkflowName, identityGeneration)
    assertWorkflowInfoIdentity(data.info, targetWorkflowName)
    upsertWorkflow(data.info)
    if (target === undefined) {
      setCurrent(data.info)
      missingPackages.value = data.missing_packages ?? []
      missingTools.value = data.missing_tools ?? []
      return data.graph
    }
    if (uiStore.canvasWorkflowId(target.canvasId) !== targetWorkflowName) {
      throw new WorkflowIdentityChangedError(targetWorkflowName)
    }
    if (
      canvasSessionRegistry.activeCanvasId.value === target.canvasId
      && currentName.value === targetWorkflowName
    ) {
      current.value = data.info
      missingPackages.value = data.missing_packages ?? []
      missingTools.value = data.missing_tools ?? []
    }
    return data.graph
  }

  function markDirty(canvasId?: CanvasId): void {
    if (canvasId !== undefined) {
      uiStore.markCanvasDirty(canvasId)
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

  async function applyWorkflowFolderIdentityMove(
    id: string,
    nextPath: string,
    previousWorkflowIds: string[],
  ): Promise<void> {
    const identityMoves = workflowIdentityMovesForFolder(previousWorkflowIds, id, nextPath)
    const requestIdentities = captureWorkflowIdentities([
      ...previousWorkflowIds,
      ...identityMoves.map(([, nextId]) => nextId),
    ])
    const previousCurrent = currentName.value
    const { data } = await api.patch<WorkflowFolderResponse>(
      `/api/v1/workflows/folders/${workflowUrl(id)}`,
      { new_path: nextPath },
    )
    assertWorkflowIdentitiesCurrent(requestIdentities)
    if (data.path !== nextPath) {
      throw new WorkflowIdentityChangedError(previousWorkflowIds[0] ?? id)
    }
    const appliedIdentities = identityMoves.length === 0
      ? requestIdentities
      : invalidateWorkflowIdentities(identityMoves.flatMap(([oldId, newId]) => [oldId, newId]))
    if (identityMoves.length > 0) forgetRetainedDrafts(previousWorkflowIds)
    const nextCurrent = previousCurrent
      ? remapWorkflowIdPrefix(previousCurrent, id, nextPath)
      : null
    await renameAutoSavesForIdentityMoves(identityMoves)
    assertWorkflowIdentitiesCurrent(appliedIdentities)
    await fetchWorkflowTree()
    if (nextCurrent) activateWorkflow(nextCurrent)
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
    const previousWorkflowIds = workflowIdsInFolderPrefix(id)
    const newPath = childFolderPath(workflowFolders.value[index].parentId, trimmed)
    if (newPath !== id) assertWorkflowIdentitiesUnmounted(previousWorkflowIds)
    await applyWorkflowFolderIdentityMove(id, newPath, previousWorkflowIds)
  }

  async function deleteWorkflowFolder(
    id: string,
    policy: WorkflowFolderDeletePolicy = 'empty',
  ): Promise<void> {
    const folder = workflowFolders.value.find((item) => item.id === id)
    if (!folder) return
    const previousWorkflowIds = workflowIdsInFolderPrefix(id)
    if (policy !== 'empty') assertWorkflowIdentitiesUnmounted(previousWorkflowIds)
    const fencedWorkflowIds = policy === 'empty' ? [] : previousWorkflowIds
    const identityMoves = policy === 'move_children_up'
      ? workflowIdentityMovesForFolder(previousWorkflowIds, id, folder.parentId)
      : []
    const destinationIdentities = captureWorkflowIdentities(
      identityMoves.map(([, destination]) => destination),
    )
    for (const workflowName of fencedWorkflowIds) {
      if (isWorkflowDeletionInFlight(workflowName)) {
        throw new Error(`Workflow '${workflowName}' is already completing a structural change.`)
      }
    }
    const fencedIdentityGenerations = invalidateWorkflowIdentities(fencedWorkflowIds)
    for (const workflowName of fencedWorkflowIds) workflowDeletionsInFlight.add(workflowName)
    const previousCurrent = currentName.value
    try {
      await api.delete(`/api/v1/workflows/folders/${workflowUrl(id)}`, {
        data: { policy },
      })
      assertWorkflowGenerationValues(fencedIdentityGenerations)
      assertWorkflowIdentitiesCurrent(destinationIdentities)
      if (policy !== 'empty') forgetRetainedDrafts(previousWorkflowIds)
      if (policy === 'delete_children') {
        await Promise.all(previousWorkflowIds.map(forgetDeletedWorkflow))
        await fetchWorkflowTree()
        return
      }
      const nextCurrent = previousCurrent
        ? remapWorkflowIdPrefix(previousCurrent, id, folder.parentId)
        : null
      const appliedDestinations = invalidateWorkflowIdentities(
        identityMoves.map(([, destination]) => destination),
      )
      await renameAutoSavesForIdentityMoves(identityMoves)
      assertWorkflowGenerationValues(fencedIdentityGenerations)
      assertWorkflowIdentitiesCurrent(appliedDestinations)
      await fetchWorkflowTree()
      if (nextCurrent) {
        activateWorkflow(nextCurrent)
      }
    } finally {
      for (const workflowName of fencedWorkflowIds) {
        workflowDeletionsInFlight.delete(workflowName)
      }
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
    const previousWorkflowIds = workflowIdsInFolderPrefix(id)
    const nextPath = childFolderPath(targetParentId, folderLeafName(id))
    if (nextPath !== id) assertWorkflowIdentitiesUnmounted(previousWorkflowIds)
    await applyWorkflowFolderIdentityMove(id, nextPath, previousWorkflowIds)
  }

  async function applyWorkflowIdentityMove(
    name: string,
    folderId: string | null,
  ): Promise<string> {
    const destination = workflowUpdateIdentity(name, {
      action: 'update',
      folder: folderId ?? '',
    }) ?? name
    const requestIdentities = captureWorkflowIdentities([name, destination])
    const wasCurrent = currentName.value === name
    const { data } = await api.patch<WorkflowInfo>(
      `/api/v1/workflows/${workflowUrl(name)}`,
      { action: 'update', folder: folderId ?? '' },
    )
    assertWorkflowIdentitiesCurrent(requestIdentities)
    assertWorkflowInfoIdentity(data, destination)
    const appliedIdentities = destination === name
      ? requestIdentities
      : invalidateWorkflowIdentities([name, destination])
    if (destination !== name) {
      forgetRetainedDrafts([name])
      await autoSave.renameWorkflow(name, destination)
      assertWorkflowIdentitiesCurrent(appliedIdentities)
    }
    upsertWorkflow(data, name)
    if (wasCurrent) {
      setCurrent(data)
      await autoSave.setLastOpenedWorkflow(destination)
    }
    return destination
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
      assertWorkflowIdentitiesUnmounted([name])
      name = await applyWorkflowIdentityMove(name, folderId)
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
      assertWorkflowIdentitiesUnmounted([name])
      name = await applyWorkflowIdentityMove(name, folderId)
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
    workflowIdentityGeneration,
    workflowServerIdentityGeneration,
    observeWorkflowServerIdentityGeneration,
    noteWorkflowStructuralEvent,
    isWorkflowIdentityCurrent,
    isWorkflowDeletionInFlight,
    assertWorkflowIdentityCurrent,
    captureWorkflowIdentity,
    activateWorkflow,
    fetchWorkflows,
    fetchWorkflowTree,
    createWorkflow,
    loadWorkflow,
    saveWorkflow,
    deleteWorkflow,
    forgetDeletedWorkflow,
    resetWorkflowPresentationGeneration,
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
