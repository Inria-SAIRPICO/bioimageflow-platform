import { computed, ref, shallowRef, type Ref } from 'vue'
import type { GraphState } from '@/api/types'
import {
  fetchWorkflowDraft,
  putWorkflowDraft,
  type WorkflowDraftResponse,
} from '@/api/workflowDrafts'
import {
  useAutoSave,
  writeAutoSaveEntry,
  type AutoSaveEntry,
} from '@/composables/useAutoSave'
import { useWorkflowStore } from '@/stores/workflow'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import {
  createRecoveryPersistenceCoordinator,
  type RecoveryPersistenceCoordinator,
} from '@/sessions/recoveryPersistenceCoordinator'
import {
  createWorkflowDraftCoordinator,
  type WorkflowDraftCoordinator,
} from '@/sessions/workflowDraftCoordinator'
import type {
  CanvasId,
  CanvasSessionDescriptor,
  DisposableCanvasResource,
} from '@/sessions/canvasSessionRegistry'
import { graphSyncCanvasSessions } from './useGraphSync'

const ROOT_PERSISTENCE_RESOURCE = 'root-persistence'

export interface CanvasPersistenceTransports {
  fetchDraft(workflowId: string): Promise<WorkflowDraftResponse>
  putDraft(
    workflowId: string,
    body: {
      graph: GraphState
      expected_revision: number
      updated_by?: 'frontend'
      validate?: boolean
    },
  ): Promise<WorkflowDraftResponse>
  writeRecovery(entry: AutoSaveEntry): Promise<void>
}

export interface CanvasScopedPersistenceOptions {
  descriptor: CanvasSessionDescriptor
  getWorkflowId: () => string | null
  transports?: CanvasPersistenceTransports
  debounceMs?: number
}

export interface CanvasPersistenceApi {
  readonly canvasId: CanvasId | null
  readonly workflowId: Ref<string | null>
  readonly currentGraph: Ref<GraphState>
  readonly isPending: Ref<boolean>
  readonly hasConflict: Ref<boolean>
  queueGraph(graph: GraphState): void
  queueDraft(graph: GraphState): void
  initializeFromDraft(response: WorkflowDraftResponse): void
  resolveFromDraft(response: WorkflowDraftResponse): void
  flush(): Promise<void>
  ensureFreshForCriticalOperation(): Promise<boolean>
  dispose(): void
}

interface RootCanvasPersistenceResource extends DisposableCanvasResource {
  readonly canvasId: CanvasId
  readonly workflowId: Ref<string | null>
  readonly currentGraph: Ref<GraphState>
  readonly isPending: Ref<boolean>
  readonly hasConflict: Ref<boolean>
  queueGraph(graph: GraphState): void
  queueDraft(graph: GraphState): void
  initializeFromDraft(response: WorkflowDraftResponse): void
  resolveFromDraft(response: WorkflowDraftResponse): void
  flush(): Promise<void>
  ensureFreshForCriticalOperation(): Promise<boolean>
}

const productionTransports: CanvasPersistenceTransports = {
  fetchDraft: fetchWorkflowDraft,
  putDraft: putWorkflowDraft,
  writeRecovery: writeAutoSaveEntry,
}

let activeFacade: CanvasPersistenceApi | null = null
let legacyFacade: CanvasPersistenceApi | null = null

export function useCanvasPersistence(
  options: CanvasScopedPersistenceOptions,
): CanvasPersistenceApi
export function useCanvasPersistence(): CanvasPersistenceApi
export function useCanvasPersistence(
  options?: CanvasScopedPersistenceOptions,
): CanvasPersistenceApi {
  if (options) return registerScopedPersistence(options)
  if (activeFacade === null) activeFacade = createActiveFacade()
  return activeFacade
}

export function _resetCanvasPersistenceForTest(): void {
  graphSyncCanvasSessions.dispose()
  activeFacade = null
  legacyFacade = null
}

function registerScopedPersistence(
  options: CanvasScopedPersistenceOptions,
): CanvasPersistenceApi {
  graphSyncCanvasSessions.register(options.descriptor)
  if (options.descriptor.kind === 'nested') {
    return createUnavailableBoundApi(options.descriptor.canvasId, () => {
      graphSyncCanvasSessions.unregister(options.descriptor.canvasId)
    })
  }
  const resource = graphSyncCanvasSessions.getOrCreateResource(
    options.descriptor.canvasId,
    ROOT_PERSISTENCE_RESOURCE,
    descriptor => createRootPersistenceResource({
      canvasId: descriptor.canvasId,
      initialWorkflowId: descriptor.kind === 'root' ? descriptor.workflowId : null,
      getWorkflowId: options.getWorkflowId,
      transports: options.transports ?? productionTransports,
      debounceMs: options.debounceMs,
    }),
  ) as RootCanvasPersistenceResource
  return createBoundApi(resource, () => {
    graphSyncCanvasSessions.unregister(options.descriptor.canvasId)
  })
}

function createRootPersistenceResource(options: {
  canvasId: CanvasId
  initialWorkflowId: string | null
  getWorkflowId: () => string | null
  transports: CanvasPersistenceTransports
  debounceMs?: number
}): RootCanvasPersistenceResource {
  const workflowId = ref<string | null>(options.initialWorkflowId)
  const currentGraph = ref<GraphState>({ nodes: [], edges: [] }) as Ref<GraphState>
  const draftCoordinator = shallowRef<WorkflowDraftCoordinator | null>(null)
  const remoteDraftRevision = ref<number | null>(null)
  const isDisposed = ref(false)
  let authoritativeDraft: WorkflowDraftResponse | null = null
  let initialization: Promise<WorkflowDraftCoordinator | null> | null = null
  let pendingDraft: { revision: number; graph: GraphState } | null = null
  const queuedDraftRevision = ref(0)
  const nextDraftRevision = ref(0)

  const recoveryCoordinator: RecoveryPersistenceCoordinator =
    createRecoveryPersistenceCoordinator({
      canvasId: options.canvasId,
      debounceMs: options.debounceMs,
      transport: async request => {
        await options.transports.writeRecovery({
          name: request.recoveryKey,
          graph: cloneGraph(request.graph),
          timestamp: request.timestamp,
        })
      },
      onOperationalError: error => {
        console.warn('[canvas-persistence] Failed to save recovery snapshot:', error)
      },
    })

  const isPending = computed(() => (
    pendingDraft !== null
      && pendingDraft.revision > queuedDraftRevision.value
  ) || draftCoordinator.value?.isPending.value === true
    || recoveryCoordinator.isPending.value)
  const hasConflict = computed(() => (
    draftCoordinator.value?.conflictDraftRevision.value !== null
    && draftCoordinator.value?.conflictDraftRevision.value !== undefined
  ) || (
    remoteDraftRevision.value !== null
    && remoteDraftRevision.value > (draftCoordinator.value?.currentDraftRevision.value ?? -1)
  ))

  function assertUsable(): void {
    if (isDisposed.value) {
      throw new Error(`Canvas persistence for '${options.canvasId}' has been disposed`)
    }
  }

  function captureWorkflowId(candidate = options.getWorkflowId()): string | null {
    assertUsable()
    if (!candidate) return workflowId.value
    if (workflowId.value !== null && workflowId.value !== candidate) {
      throw new Error(
        `Canvas '${options.canvasId}' cannot change workflow from '${workflowId.value}' to '${candidate}'`,
      )
    }
    workflowId.value = candidate
    return candidate
  }

  function queuePendingDraft(coordinator: WorkflowDraftCoordinator): void {
    if (
      pendingDraft === null
      || pendingDraft.revision <= queuedDraftRevision.value
    ) return
    coordinator.queue(pendingDraft.graph)
    queuedDraftRevision.value = pendingDraft.revision
  }

  async function ensureDraftCoordinator(): Promise<WorkflowDraftCoordinator | null> {
    assertUsable()
    if (draftCoordinator.value !== null) return draftCoordinator.value
    if (initialization !== null) return initialization
    const capturedId = captureWorkflowId()
    if (capturedId === null) return null
    const initial = authoritativeDraft
    initialization = (async () => {
      const response = initial ?? await options.transports.fetchDraft(capturedId)
      assertUsable()
      if (response.workflow_id !== capturedId) {
        throw new Error(`Draft response '${response.workflow_id}' does not match '${capturedId}'`)
      }
      const coordinator = createWorkflowDraftCoordinator({
        canvasId: options.canvasId,
        workflowId: capturedId,
        initialDraftRevision: response.draft_revision,
        debounceMs: options.debounceMs,
        transport: request => options.transports.putDraft(request.workflowId, {
          graph: cloneGraph(request.graph),
          expected_revision: request.expectedDraftRevision,
          updated_by: 'frontend',
        }),
        onOperationalError: error => {
          console.warn('[canvas-persistence] Failed to save workflow draft:', error)
        },
      })
      draftCoordinator.value = coordinator
      queuePendingDraft(coordinator)
      return coordinator
    })().catch((error) => {
      initialization = null
      throw error
    })
    return initialization
  }

  function queueDraft(graph: GraphState): void {
    const capturedId = captureWorkflowId()
    if (capturedId === null) return
    const snapshot = cloneGraph(graph)
    currentGraph.value = cloneGraph(snapshot)
    nextDraftRevision.value += 1
    pendingDraft = { revision: nextDraftRevision.value, graph: snapshot }
    void ensureDraftCoordinator().then((coordinator) => {
      if (coordinator !== null && !isDisposed.value) queuePendingDraft(coordinator)
    }).catch(() => {
      // The retained snapshot is retried by flush or the next queue.
    })
  }

  function queueGraph(graph: GraphState): void {
    const capturedId = captureWorkflowId()
    if (capturedId === null) return
    queueDraft(graph)
    recoveryCoordinator.queue(capturedId, graph)
  }

  function initializeFromDraft(response: WorkflowDraftResponse): void {
    const capturedId = captureWorkflowId(response.workflow_id)
    if (capturedId === null) return
    if (draftCoordinator.value !== null) {
      if (response.draft_revision > draftCoordinator.value.currentDraftRevision.value) {
        remoteDraftRevision.value = response.draft_revision
      }
      return
    }
    authoritativeDraft = cloneJson(response)
  }

  function resolveFromDraft(response: WorkflowDraftResponse): void {
    const capturedId = captureWorkflowId(response.workflow_id)
    if (capturedId === null) return
    draftCoordinator.value?.dispose()
    draftCoordinator.value = null
    initialization = null
    authoritativeDraft = cloneJson(response)
    remoteDraftRevision.value = null
    pendingDraft = null
    queuedDraftRevision.value = 0
    nextDraftRevision.value = 0
    currentGraph.value = cloneGraph(response.graph)
    recoveryCoordinator.queue(capturedId, response.graph)
  }

  async function flush(): Promise<void> {
    assertUsable()
    const coordinator = await ensureDraftCoordinator()
    if (coordinator !== null) queuePendingDraft(coordinator)
    await Promise.all([
      coordinator?.flushLatest(),
      recoveryCoordinator.flushLatest(),
    ])
  }

  async function ensureFreshForCriticalOperation(): Promise<boolean> {
    assertUsable()
    try {
      await flush()
    } catch (error) {
      if (isConflict(error)) return false
      throw error
    }
    const coordinator = draftCoordinator.value
    const capturedId = workflowId.value
    if (coordinator === null || capturedId === null || hasConflict.value) return false
    const latest = await options.transports.fetchDraft(capturedId)
    if (latest.draft_revision > coordinator.currentDraftRevision.value) {
      remoteDraftRevision.value = latest.draft_revision
      return false
    }
    remoteDraftRevision.value = null
    return true
  }

  function dispose(): void {
    if (isDisposed.value) return
    isDisposed.value = true
    draftCoordinator.value?.dispose()
    recoveryCoordinator.dispose()
  }

  return {
    canvasId: options.canvasId,
    workflowId,
    currentGraph,
    isPending,
    hasConflict,
    queueGraph,
    queueDraft,
    initializeFromDraft,
    resolveFromDraft,
    flush,
    ensureFreshForCriticalOperation,
    dispose,
  }
}

function createBoundApi(
  resource: RootCanvasPersistenceResource,
  dispose: () => void,
): CanvasPersistenceApi {
  return {
    canvasId: resource.canvasId,
    workflowId: resource.workflowId,
    currentGraph: resource.currentGraph,
    isPending: resource.isPending,
    hasConflict: resource.hasConflict,
    queueGraph: graph => resource.queueGraph(graph),
    queueDraft: graph => resource.queueDraft(graph),
    initializeFromDraft: response => resource.initializeFromDraft(response),
    resolveFromDraft: response => resource.resolveFromDraft(response),
    flush: () => resource.flush(),
    ensureFreshForCriticalOperation: () => (
      resource.ensureFreshForCriticalOperation()
    ),
    dispose,
  }
}

function createUnavailableBoundApi(
  canvasId: CanvasId,
  dispose: () => void,
): CanvasPersistenceApi {
  const workflowId = ref<string | null>(null)
  const currentGraph = ref<GraphState>({ nodes: [], edges: [] }) as Ref<GraphState>
  return {
    canvasId,
    workflowId,
    currentGraph,
    isPending: ref(false),
    hasConflict: ref(false),
    queueGraph: () => {},
    queueDraft: () => {},
    initializeFromDraft: () => {},
    resolveFromDraft: () => {},
    flush: async () => {},
    ensureFreshForCriticalOperation: async () => false,
    dispose,
  }
}

function createActiveFacade(): CanvasPersistenceApi {
  const selected = (): CanvasPersistenceApi | null => {
    const activeCanvasId = graphSyncCanvasSessions.activeCanvasId.value
    if (activeCanvasId !== null) {
      const session = graphSyncCanvasSessions.get(activeCanvasId)
      if (session?.descriptor.kind !== 'root') return null
      const resource = graphSyncCanvasSessions.getResource<RootCanvasPersistenceResource>(
        activeCanvasId,
        ROOT_PERSISTENCE_RESOURCE,
      )
      return resource === null
        ? null
        : createBoundApi(resource, () => graphSyncCanvasSessions.unregister(activeCanvasId))
    }
    if (graphSyncCanvasSessions.sessionCount.value === 0) return getLegacyFacade()
    return null
  }
  const required = (): CanvasPersistenceApi => {
    const target = selected()
    if (target === null) throw new Error('No active root canvas persistence session')
    return target
  }
  return {
    get canvasId() {
      return graphSyncCanvasSessions.activeCanvasId.value
    },
    workflowId: computed(() => selected()?.workflowId.value ?? null),
    currentGraph: computed(() => selected()?.currentGraph.value ?? { nodes: [], edges: [] }),
    isPending: computed(() => selected()?.isPending.value ?? false),
    hasConflict: computed(() => selected()?.hasConflict.value ?? false),
    queueGraph: graph => required().queueGraph(graph),
    queueDraft: graph => required().queueDraft(graph),
    initializeFromDraft: response => required().initializeFromDraft(response),
    resolveFromDraft: response => required().resolveFromDraft(response),
    flush: () => required().flush(),
    ensureFreshForCriticalOperation: async () => (
      selected()?.ensureFreshForCriticalOperation() ?? false
    ),
    dispose: () => required().dispose(),
  }
}

function getLegacyFacade(): CanvasPersistenceApi {
  if (legacyFacade !== null) return legacyFacade
  const workflowId = computed(() => {
    try {
      return useWorkflowStore().currentName
    } catch {
      return null
    }
  })
  const currentGraph = ref<GraphState>({ nodes: [], edges: [] }) as Ref<GraphState>
  const isPending = computed(() => {
    try {
      return useWorkflowDraftStore().hasPendingSave
    } catch {
      return false
    }
  })
  const hasConflict = computed(() => {
    try {
      return useWorkflowDraftStore().isStale
    } catch {
      return false
    }
  })
  function queueDraft(graph: GraphState): void {
    const id = workflowId.value
    if (!id) return
    currentGraph.value = cloneGraph(graph)
    useWorkflowDraftStore().scheduleSave(id, graph)
  }
  legacyFacade = {
    canvasId: null,
    workflowId,
    currentGraph,
    isPending,
    hasConflict,
    queueGraph: graph => {
      const id = workflowId.value
      if (!id) return
      queueDraft(graph)
      useAutoSave().scheduleAutoSave(id, graph)
    },
    queueDraft,
    initializeFromDraft: () => {},
    resolveFromDraft: () => {},
    flush: async () => {
      await Promise.all([
        useWorkflowDraftStore().flush(),
        useAutoSave().flushAutoSave(),
      ])
    },
    ensureFreshForCriticalOperation: () => (
      useWorkflowDraftStore().ensureFreshForCriticalOperation(workflowId.value)
    ),
    dispose: () => {},
  }
  return legacyFacade
}

function isConflict(error: unknown): boolean {
  return typeof error === 'object'
    && error !== null
    && 'response' in error
    && (error as { response?: { status?: unknown } }).response?.status === 409
}

function cloneGraph(graph: GraphState): GraphState {
  return cloneJson(graph)
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}
