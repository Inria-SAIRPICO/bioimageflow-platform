import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import { AxiosError } from 'axios'
import { api } from '@/api/client'
import { useAutoSave } from '@/composables/useAutoSave'
import { useUIStore } from '@/stores/ui'
import { useSettingsStore } from '@/stores/settings'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import {
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'
import { clearRecoveryPersistenceKeyStrict } from '@/sessions/recoveryPersistenceCoordinator'
import { recoveryOwnerKey, type AutoSaveOwner } from '@/sessions/recoveryIdentity'
import type {
  GraphState,
  MissingPackage,
  MissingTool,
  WorkflowCreate,
  WorkflowFile,
  WorkflowInfo,
  WorkflowImportResponse,
  WorkflowResultsFolderExportRequest,
  WorkflowResultsFolderExportResponse,
  WorkflowUpdate,
} from '@/api/types'

export type WorkflowPresentationCause = 'startup' | 'foreground' | 'passive'

export interface WorkflowPresentationPublication {
  readonly sequence: number
  readonly workflowName: string
  readonly cause: Exclude<WorkflowPresentationCause, 'passive'>
}

type WorkflowInfoWithTreeFields = WorkflowInfo & {
  id?: string | null
  folder?: string
  workspace_path?: string | null
  results_path: string
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

export function workflowRelativePath(workflow: WorkflowInfo): string {
  return workflow.relative_path
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

function workflowExportFilename(name: string, suffix: string): string {
  const separator = name.lastIndexOf('/')
  const leaf = separator === -1 ? name : name.slice(separator + 1)
  return `${leaf || 'workflow'}${suffix}`
}

export const useWorkflowStore = defineStore('workflow', () => {
  const workflows = ref<WorkflowInfo[]>([])
  const workflowFolders = ref<WorkflowFolder[]>([])
  const workflowFolderIds = ref<Record<string, string | null>>({})
  const workflowOrder = ref<string[]>([])
  const current = ref<WorkflowInfo | null>(null)
  const selectedFolderId = ref<string | null>(null)
  const presentationPublication = shallowRef<WorkflowPresentationPublication | null>(null)
  let presentationSequence = 0
  const missingPackages = ref<MissingPackage[]>([])
  const missingTools = ref<MissingTool[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const workflowIdentityGenerations = new Map<string, number>()
  const identityMutationSequences = new Map<string, number>()
  let identityMutationSequence = 0
  const workflowServerIdentityGenerations = new Map<string, number>()
  const workflowDeletionsInFlight = new Set<string>()
  const workflowRemovalPromises = new Map<string, Promise<void>>()
  const workflowPresentationResetPromises = new Map<string, Promise<void>>()
  let workflowCollectionGeneration = 0
  let catalogAuthorityEpoch = 0
  let catalogMessageOwner = 0
  const pendingCatalogReads = new Set<number>()
  type CatalogReadResult<T> = { current: true; value: T } | { current: false }
  let pendingTreeRead: {
    generation: number
    epoch: number
    workspaceSelection: number
    promise: Promise<CatalogReadResult<WorkflowTreeNode[]>>
  } | null = null

  function noteCatalogAuthorityChange(): void {
    catalogAuthorityEpoch += 1
  }

  const uiStore = useUIStore()
  const autoSave = useAutoSave()

  function captureWorkspaceSelection(): number {
    return useSettingsStore().workspaceSelectionRevision
  }

  function assertWorkspaceSelectionCurrent(selection: number): void {
    if (selection !== captureWorkspaceSelection()) {
      throw new Error('The workspace changed while the operation was pending. Refresh the selected workspace to see its workflows.')
    }
  }

  function captureRecoveryOwner(name: string): AutoSaveOwner | undefined {
    const info = workflowByName.value.get(name)
    const workspace = info?.workspace_path
    const generation = info?.identity_generation ?? workflowServerIdentityGeneration(name)
    return workspace && generation !== null && generation !== undefined
      ? { workspace_path: workspace, identity_generation: generation }
      : undefined
  }

  function clearOwnedRecovery(name: string, owner: AutoSaveOwner | undefined): Promise<void> {
    return clearRecoveryPersistenceKeyStrict(
      owner ? recoveryOwnerKey(name, owner) : JSON.stringify(['unresolved', name]),
      () => autoSave.clearAutoSaveStrict(name, ...(owner ? [owner] : [])),
    )
  }

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
      if (options.structuralEvent) noteWorkflowStructuralEvent()
    }
    return true
  }

  function noteWorkflowStructuralEvent(): void {
    workflowCollectionGeneration += 1
    noteCatalogAuthorityChange()
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
    identityMutationSequences.set(name, ++identityMutationSequence)
    noteWorkflowStructuralEvent()
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
      .filter((workflow) => {
        const path = workflowRelativePath(workflow)
        return path === folderId || path.startsWith(`${folderId}/`)
      })
      .map(workflowId)
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
      `Close the affected workflow and nested-workflow tabs before renaming, moving, or deleting ${names}.`,
    )
  }

  function workflowUpdateIdentity(name: string, patch: WorkflowUpdate): string | null {
    if (patch.action !== 'update') return null
    if (patch.new_id !== null && patch.new_id !== undefined) return patch.new_id
    if (patch.new_name == null && patch.folder == null) return null
    const path = workflowByName.value.get(name)
    const currentPath = path ? workflowRelativePath(path) : name
    const currentFolder = parentFolderPath(currentPath)
    if (patch.new_name !== null && patch.new_name !== undefined) {
      const targetFolder = patch.folder !== null && patch.folder !== undefined
        ? patch.folder
        : currentFolder
      const leaf = folderLeafName(patch.new_name)
      return targetFolder ? `${targetFolder}/${leaf}` : leaf
    }
    if (patch.folder !== null && patch.folder !== undefined) {
      const leaf = folderLeafName(currentPath)
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

  function assertWorkflowInfoIdentity(info: WorkflowInfo, expectedId: string): void {
    if (workflowId(info) !== expectedId || !acceptWorkflowInfoGeneration(info)) {
      throw new WorkflowIdentityChangedError(expectedId)
    }
  }

  function remapWorkflowIdPrefix(id: string, oldPrefix: string, newPrefix: string | null): string {
    if (id === oldPrefix) return newPrefix ?? ''
    if (!id.startsWith(`${oldPrefix}/`)) return id
    const suffix = id.slice(oldPrefix.length + 1)
    return newPrefix ? `${newPrefix}/${suffix}` : suffix
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
    noteCatalogAuthorityChange()
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
    workflowFolderIds.value[infoId] = workflowFolderPath(info)
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

  function setCurrent(
    info: WorkflowInfo | null,
    canvasId?: CanvasId,
    cause: WorkflowPresentationCause = 'passive',
  ): void {
    if (info && cause !== 'passive') {
      // Consume deliberate/startup intent before the paired metadata assignment.
      presentationPublication.value = Object.freeze({
        sequence: ++presentationSequence, workflowName: workflowId(info), cause,
      })
    } else {
      // Passive metadata cannot leave a stale intent paired with a later write.
      presentationPublication.value = null
    }
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

  function activateWorkflow(
    name: string,
    canvasId?: CanvasId,
    cause: WorkflowPresentationCause = 'foreground',
  ): WorkflowInfo | null {
    const info = workflows.value.find((workflow) => workflowId(workflow) === name) ?? null
    if (info) {
      setCurrent(info, canvasId, cause)
    }
    return info
  }

  async function readWorkflowCatalog<T, V>(
    url: string,
    apply: (data: T) => V,
  ): Promise<CatalogReadResult<V>> {
    const generation = workflowCollectionGeneration
    const epoch = catalogAuthorityEpoch
    const workspaceSelection = captureWorkspaceSelection()
    const ownerWorkspace = useSettingsStore().settings?.workspace_path
    const owner = ++catalogMessageOwner
    pendingCatalogReads.add(owner)
    isLoading.value = true
    const isCurrent = () => generation === workflowCollectionGeneration
      && epoch === catalogAuthorityEpoch
      && workspaceSelection === captureWorkspaceSelection()
    try {
      const { data } = await api.get<T>(url,
        ...(ownerWorkspace ? [{ headers: { 'X-BioImageFlow-Workspace': ownerWorkspace } }] : []),
      )
      if (!isCurrent()) return { current: false }
      const value = apply(data)
      noteCatalogAuthorityChange()
      if (owner === catalogMessageOwner) error.value = null
      return { current: true, value }
    } catch (err: unknown) {
      if (isCurrent() && owner === catalogMessageOwner) {
        error.value = err instanceof Error ? err.message : String(err)
      }
      throw err
    } finally {
      pendingCatalogReads.delete(owner)
      isLoading.value = pendingCatalogReads.size > 0
    }
  }

  async function fetchWorkflows(): Promise<WorkflowInfo[]> {
    const workspaceSelection = captureWorkspaceSelection()
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const result = await readWorkflowCatalog<WorkflowInfo[], WorkflowInfo[]>(
        '/api/v1/workflows',
        (data) => {
          applyWorkflowList(data)
          return data
        },
      )
      assertWorkspaceSelectionCurrent(workspaceSelection)
      if (result.current) return result.value
    }
    throw new Error('Workflow identities changed while refreshing the workflow list.')
  }

  function pendingWorkflowTreeRead(): Promise<CatalogReadResult<WorkflowTreeNode[]>> {
    if (pendingTreeRead?.epoch === catalogAuthorityEpoch
      && pendingTreeRead.generation === workflowCollectionGeneration
      && pendingTreeRead.workspaceSelection === captureWorkspaceSelection()) {
      return pendingTreeRead.promise
    }
    const entry = {
      generation: workflowCollectionGeneration,
      epoch: catalogAuthorityEpoch,
      workspaceSelection: captureWorkspaceSelection(),
      promise: readWorkflowCatalog<WorkflowFolderResponse, WorkflowTreeNode[]>(
        '/api/v1/workflows/tree',
        (data) => {
          applyWorkflowTree(data)
          return workflowTree.value
        },
      ),
    }
    entry.promise = entry.promise.finally(() => {
      // Relinquish this flight before a stale result can admit a retry.
      if (pendingTreeRead === entry) pendingTreeRead = null
    })
    pendingTreeRead = entry
    return entry.promise
  }

  async function fetchWorkflowTree(
    options: { fresh?: boolean } = {},
  ): Promise<WorkflowTreeNode[]> {
    const workspaceSelection = captureWorkspaceSelection()
    if (options.fresh) noteCatalogAuthorityChange()
    // Retry belongs to each caller; a shared flight never resets this budget.
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const result = await pendingWorkflowTreeRead()
      assertWorkspaceSelectionCurrent(workspaceSelection)
      if (result.current) return result.value
    }
    throw new Error('Workflow identities changed while refreshing the workflow tree.')
  }

  async function createWorkflow(
    body: WorkflowCreate,
    canvasId?: CanvasId,
  ): Promise<WorkflowInfo> {
    const issuedAt = identityMutationSequence
    const workspaceSelection = useSettingsStore().workspaceSelectionRevision
    try {
      const { data } = await api.post<WorkflowInfo>('/api/v1/workflows', body)
      const createdName = workflowId(data)
      if ((identityMutationSequences.get(createdName) ?? 0) > issuedAt) throw new WorkflowIdentityChangedError(createdName)
      const expectedWorkspace = (body as WorkflowCreate & { expected_workspace_path?: string }).expected_workspace_path
      if (useSettingsStore().workspaceSelectionRevision !== workspaceSelection
        || (expectedWorkspace && data.workspace_path && expectedWorkspace !== data.workspace_path)) {
        throw new Error('The workflow was created in the original workspace. Switch back to that workspace to open it.')
      }
      if (!acceptWorkflowInfoGeneration(data)) throw new WorkflowIdentityChangedError(createdName)
      const identityGeneration = invalidateWorkflowIdentity(createdName)
      upsertWorkflow(data)
      setCurrent(data, canvasId, 'foreground')
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
    options: { rememberAsLastOpened?: boolean; canUpdatePresentation?: () => boolean; presentationCause?: WorkflowPresentationCause } = {},
  ): Promise<GraphState> {
    const identityGeneration = captureWorkflowIdentity(name)
    const workspaceSelection = useSettingsStore().workspaceSelectionRevision
    const ownerWorkspace = workflowByName.value.get(name)?.workspace_path ?? useSettingsStore().settings?.workspace_path
    const { data } = await api.get<WorkflowFile>(`/api/v1/workflows/${workflowUrl(name)}`,
      ...(ownerWorkspace ? [{ headers: { 'X-BioImageFlow-Workspace': ownerWorkspace } }] : []))
    if (useSettingsStore().workspaceSelectionRevision !== workspaceSelection) throw new WorkflowIdentityChangedError(name)
    assertWorkflowIdentityCurrent(name, identityGeneration)
    if (workflowId(data.info) !== name) {
      throw new WorkflowIdentityChangedError(name)
    }
    upsertWorkflow(data.info)
    if (options.canUpdatePresentation?.() !== false) {
      setCurrent(data.info, canvasId, options.presentationCause ?? 'foreground')
      missingPackages.value = data.missing_packages ?? []
      missingTools.value = data.missing_tools ?? []
      markPresentationClean(canvasId)
    }
    if (options.rememberAsLastOpened !== false) {
      await autoSave.setLastOpenedWorkflow(name)
    }
    if (useSettingsStore().workspaceSelectionRevision !== workspaceSelection) throw new WorkflowIdentityChangedError(name)
    assertWorkflowIdentityCurrent(name, identityGeneration)
    return data.graph
  }

  async function refreshWorkflowDependencies(name: string): Promise<void> {
    const identityGeneration = captureWorkflowIdentity(name)
    const { data } = await api.get<WorkflowFile>(`/api/v1/workflows/${workflowUrl(name)}`)
    assertWorkflowIdentityCurrent(name, identityGeneration)
    if (workflowId(data.info) !== name) {
      throw new WorkflowIdentityChangedError(name)
    }
    upsertWorkflow(data.info)
    if (currentName.value === name) {
      setCurrent(data.info)
      missingPackages.value = data.missing_packages ?? []
      missingTools.value = data.missing_tools ?? []
    }
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
    const workspaceSelection = useSettingsStore().workspaceSelectionRevision
    const owner = captureRecoveryOwner(targetWorkflowName)
    const ownerWorkspace = owner?.workspace_path ?? useSettingsStore().settings?.workspace_path
    const { data } = await api.put<WorkflowInfo>(
      `/api/v1/workflows/${workflowUrl(targetWorkflowName)}`,
      { graph },
      ...(ownerWorkspace ? [{ headers: { 'X-BioImageFlow-Workspace': ownerWorkspace } }] : []),
    )
    if (useSettingsStore().workspaceSelectionRevision !== workspaceSelection) throw new WorkflowIdentityChangedError(targetWorkflowName)
    assertWorkflowIdentityCurrent(targetWorkflowName, identityGeneration)
    if (workflowId(data) !== targetWorkflowName) {
      throw new WorkflowIdentityChangedError(targetWorkflowName)
    }
    upsertWorkflow(data)
    await autoSave.clearAutoSave(workflowId(data), ...(owner ? [owner] : []))
    if (useSettingsStore().workspaceSelectionRevision !== workspaceSelection) throw new WorkflowIdentityChangedError(targetWorkflowName)
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
      setCurrent(data)
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
    const recoveryOwner = captureRecoveryOwner(name)

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
        await clearOwnedRecovery(name, recoveryOwner)
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
    const recoveryOwner = captureRecoveryOwner(name)

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
        await clearOwnedRecovery(name, recoveryOwner)
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

  async function exportWorkflow(name: string, signal?: AbortSignal): Promise<void> {
    await downloadWorkflowExport(
      name,
      `/api/v1/workflows/${workflowUrl(name)}/export`,
      workflowExportFilename(name, '.bioimageflow.zip'),
      signal,
    )
  }

  async function downloadWorkflowExport(
    name: string,
    url: string,
    fallbackFilename: string,
    signal?: AbortSignal,
  ): Promise<void> {
    const response = await api.post<Blob>(
      url,
      undefined,
      signal ? { responseType: 'blob', signal } : { responseType: 'blob' },
    )
    const filename = filenameFromDisposition(
      response.headers?.['content-disposition'],
      fallbackFilename,
    )
    downloadBlob(response.data, filename)
  }

  async function exportLatestResults(name: string, signal?: AbortSignal): Promise<void> {
    await downloadWorkflowExport(
      name,
      `/api/v1/workflows/${workflowUrl(name)}/exports/latest-results`,
      workflowExportFilename(name, '.latest-results.zip'),
      signal,
    )
  }

  async function exportSuccessfulRunResults(name: string, signal?: AbortSignal): Promise<void> {
    await downloadWorkflowExport(
      name,
      `/api/v1/workflows/${workflowUrl(name)}/exports/successful-run-results`,
      workflowExportFilename(name, '.successful-run-results.zip'),
      signal,
    )
  }

  async function exportWorkflowRunBundle(name: string, signal?: AbortSignal): Promise<void> {
    await downloadWorkflowExport(
      name,
      `/api/v1/workflows/${workflowUrl(name)}/exports/workflow-run-bundle`,
      workflowExportFilename(name, '.workflow-run.zip'),
      signal,
    )
  }

  async function exportLatestResultsToFolder(
    name: string,
    destinationParent: string,
    replace = false,
    signal?: AbortSignal,
  ): Promise<WorkflowResultsFolderExportResponse> {
    const request: WorkflowResultsFolderExportRequest = {
      destination_parent: destinationParent,
      replace,
    }
    const { data } = await api.post<WorkflowResultsFolderExportResponse>(
      `/api/v1/workflows/${workflowUrl(name)}/exports/latest-results-folder`,
      request,
      { signal },
    )
    return data
  }

  async function importWorkflow(
    file: File,
    options: { nameOverride?: string } = {},
  ): Promise<WorkflowImportResponse> {
    const issuedAt = identityMutationSequence
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
      const importedId = workflowId(data.info)
      if ((identityMutationSequences.get(importedId) ?? 0) > issuedAt) throw new WorkflowIdentityChangedError(importedId)
      if (!acceptWorkflowInfoGeneration(data.info)) throw new WorkflowIdentityChangedError(importedId)
      const identityGeneration = invalidateWorkflowIdentity(importedId)
      upsertWorkflow(data.info)
      missingPackages.value = data.missing_packages ?? []
      missingTools.value = data.missing_tools ?? []
      assertWorkflowIdentityCurrent(importedId, identityGeneration)
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
    const workspaceSelection = captureWorkspaceSelection()
    const ownerWorkspace = workflowByName.value.get(name)?.workspace_path ?? useSettingsStore().settings?.workspace_path
    const requestIdentities = captureWorkflowIdentities([name])
    const issuedAt = identityMutationSequence
    const apply = async () => {
      assertWorkspaceSelectionCurrent(workspaceSelection)
      const { data } = await api.patch<WorkflowInfo>(
        `/api/v1/workflows/${workflowUrl(name)}`,
        patch,
        ...(ownerWorkspace ? [{ headers: { 'X-BioImageFlow-Workspace': ownerWorkspace } }] : []),
      )
      assertWorkspaceSelectionCurrent(workspaceSelection)
      assertWorkflowIdentitiesCurrent(requestIdentities)
      const dataId = workflowId(data)
      if (patch.action === 'update') assertWorkflowInfoIdentity(data, name)
      else {
        if ((identityMutationSequences.get(dataId) ?? 0) > issuedAt) throw new WorkflowIdentityChangedError(dataId)
        if (!acceptWorkflowInfoGeneration(data)) throw new WorkflowIdentityChangedError(dataId)
        invalidateWorkflowIdentity(dataId)
      }
      upsertWorkflow(data)
      if (target === undefined) {
        if (patch.action === 'update' && currentName.value === name) setCurrent(data)
        return data
      }
      if (uiStore.canvasWorkflowId(target.canvasId) !== target.workflowName) return data
      uiStore.setCanvasWorkflow(target.canvasId, dataId, data.display_name)
      if (canvasSessionRegistry.activeCanvasId.value === target.canvasId
        && currentName.value === target.workflowName) {
        setCurrent(data)
        await autoSave.setLastOpenedWorkflow(dataId)
      }
      return data
    }
    try {
      if (patch.action === 'update' && workflowUpdateIdentity(name, patch) !== null) {
        const { withWorkflowMove } = await import('@/services/workflowMove')
        return await withWorkflowMove([name], apply)
      }
      return await apply()
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
      setCurrent(data.info)
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
    const workspaceSelection = captureWorkspaceSelection()
    const ownerWorkspace = useSettingsStore().settings?.workspace_path
    const path = childFolderPath(parentId, trimmed)
    const { data } = await api.post<WorkflowFolderResponse>('/api/v1/workflows/folders', {
      path,
    }, ...(ownerWorkspace ? [{ headers: { 'X-BioImageFlow-Workspace': ownerWorkspace } }] : []))
    assertWorkspaceSelectionCurrent(workspaceSelection)
    const folder: WorkflowFolder = {
      id: data.path,
      name: data.display_name,
      parentId: parentFolderPath(data.path),
    }
    noteCatalogAuthorityChange()
    workflowFolders.value = [...workflowFolders.value, folder]
    return folder
  }

  async function applyWorkflowFolderIdentityMove(
    id: string,
    nextPath: string,
    previousWorkflowIds: string[],
  ): Promise<void> {
    const workspaceSelection = captureWorkspaceSelection()
    const ownerWorkspace = workflows.value.find(workflow => previousWorkflowIds.includes(workflowId(workflow)))?.workspace_path ?? useSettingsStore().settings?.workspace_path
    const requestIdentities = captureWorkflowIdentities(previousWorkflowIds)
    const previousCurrent = currentName.value
    const { withWorkflowMove } = await import('@/services/workflowMove')
    await withWorkflowMove(previousWorkflowIds, async () => {
      assertWorkspaceSelectionCurrent(workspaceSelection)
      const { data } = await api.patch<WorkflowFolderResponse>(
        `/api/v1/workflows/folders/${workflowUrl(id)}`,
        { new_path: nextPath },
        ...(ownerWorkspace ? [{ headers: { 'X-BioImageFlow-Workspace': ownerWorkspace } }] : []),
      )
      assertWorkspaceSelectionCurrent(workspaceSelection)
      assertWorkflowIdentitiesCurrent(requestIdentities)
      if (data.path !== nextPath) throw new Error('The folder move returned a different destination.')
      if (selectedFolderId.value) selectedFolderId.value = remapWorkflowIdPrefix(selectedFolderId.value, id, nextPath)
      await fetchWorkflowTree({ fresh: true })
      assertWorkspaceSelectionCurrent(workspaceSelection)
      if (previousCurrent) activateWorkflow(previousCurrent, undefined, 'passive')
    })
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
    await applyWorkflowFolderIdentityMove(id, newPath, previousWorkflowIds)
  }

  async function deleteWorkflowFolder(
    id: string,
    policy: WorkflowFolderDeletePolicy = 'empty',
  ): Promise<void> {
    const folder = workflowFolders.value.find(item => item.id === id)
    if (!folder) return
    const previousWorkflowIds = workflowIdsInFolderPrefix(id)
    if (policy === 'delete_children') assertWorkflowIdentitiesUnmounted(previousWorkflowIds)
    const workspaceSelection = captureWorkspaceSelection()
    const ownerWorkspace = workflows.value.find(workflow => previousWorkflowIds.includes(workflowId(workflow)))?.workspace_path ?? useSettingsStore().settings?.workspace_path
    const requestIdentities = captureWorkflowIdentities(previousWorkflowIds)
    const previousCurrent = currentName.value
    const apply = async () => {
      assertWorkspaceSelectionCurrent(workspaceSelection)
      await api.delete(`/api/v1/workflows/folders/${workflowUrl(id)}`, { data: { policy }, ...(ownerWorkspace ? { headers: { 'X-BioImageFlow-Workspace': ownerWorkspace } } : {}) })
      assertWorkspaceSelectionCurrent(workspaceSelection)
      assertWorkflowIdentitiesCurrent(requestIdentities)
      if (policy === 'delete_children') {
        for (const workflowId of previousWorkflowIds) invalidateWorkflowIdentity(workflowId)
        const drafts = useWorkflowDraftStore()
        for (const workflowId of previousWorkflowIds) drafts.forgetWorkflow(workflowId)
        await Promise.all(previousWorkflowIds.map(forgetDeletedWorkflow))
      }
      assertWorkspaceSelectionCurrent(workspaceSelection)
      if (selectedFolderId.value) selectedFolderId.value = remapWorkflowIdPrefix(selectedFolderId.value, id, folder.parentId)
      await fetchWorkflowTree({ fresh: true })
      assertWorkspaceSelectionCurrent(workspaceSelection)
      if (previousCurrent && policy !== 'delete_children') activateWorkflow(previousCurrent, undefined, 'passive')
    }
    if (policy === 'move_children_up') {
      const { withWorkflowMove } = await import('@/services/workflowMove')
      await withWorkflowMove(previousWorkflowIds, apply)
    } else await apply()
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
    await applyWorkflowFolderIdentityMove(id, nextPath, previousWorkflowIds)
  }

  async function applyWorkflowIdentityMove(
    name: string,
    folderId: string | null,
  ): Promise<string> {
    await patchWorkflow(name, { action: 'update', folder: folderId ?? '' })
    return name
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
    const workspaceSelection = captureWorkspaceSelection()
    const previousFolderId = workflowFolderId(name)
    if (previousFolderId !== folderId) {
      name = await applyWorkflowIdentityMove(name, folderId)
      assertWorkspaceSelectionCurrent(workspaceSelection)
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
    const workspaceSelection = captureWorkspaceSelection()
    const previousFolderId = workflowFolderId(name)
    if (previousFolderId !== folderId) {
      name = await applyWorkflowIdentityMove(name, folderId)
      assertWorkspaceSelectionCurrent(workspaceSelection)
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
    selectedFolderId,
    currentName,
    presentationPublication: computed(() => presentationPublication.value),
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
    refreshWorkflowDependencies,
    saveWorkflow,
    deleteWorkflow,
    forgetDeletedWorkflow,
    resetWorkflowPresentationGeneration,
    exportWorkflow,
    exportLatestResults,
    exportWorkflowRunBundle,
    exportSuccessfulRunResults,
    exportLatestResultsToFolder,
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
