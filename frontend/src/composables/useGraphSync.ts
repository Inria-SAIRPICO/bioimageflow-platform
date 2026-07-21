import { computed, nextTick, type Ref } from 'vue'
import {
  getOrCreateRootPersistenceResource,
  ROOT_PERSISTENCE_RESOURCE,
  type RootCanvasPersistenceResource,
} from '@/composables/useCanvasPersistence'
import {
  canvasSessionRegistry,
  type CanvasId,
  type CanvasSessionDescriptor,
} from '@/sessions/canvasSessionRegistry'
import {
  type SyncState,
} from '@/sessions/graphSyncCoordinator'
import {
  createNestedSnapshotPersistence,
  type AcceptedNestedSnapshot,
  type NestedSnapshotPersistence,
} from '@/sessions/nestedSnapshotPersistence'
import type { NestedWorkflowSnapshotResponse } from '@/api/nestedWorkflowSnapshots'
import { emptyGraph, graphDocumentsEqual } from '@/sessions/graphDocument'
import type {
  ColumnEdge,
  DataFrameEdge,
  GraphState,
  ToolNodeState,
  ValidationResult,
  WorkflowNodeState,
} from '@/api/types'
import { decodeEndpointHandle } from '@/utils/endpointHandles'

type Edge = ColumnEdge | DataFrameEdge
type NodeState = ToolNodeState | WorkflowNodeState

export type { SyncState } from '@/sessions/graphSyncCoordinator'

export interface CanvasScopedGraphSyncOptions {
  descriptor: CanvasSessionDescriptor
  getWorkflowId: () => string | null
  nestedSnapshot?: {
    initialSnapshot: NestedWorkflowSnapshotResponse
    onAccepted?: (snapshot: NestedWorkflowSnapshotResponse) => void
  }
}

export type AcceptedGraphSnapshot = AcceptedNestedSnapshot | {
  graph: GraphState
  validation: ValidationResult
  snapshotRevision: null
}

export interface GraphSyncApi {
  syncGraph(graph: Parameters<typeof serializeGraph>[0]): void
  syncGraphState(graph: GraphState): void
  revalidateGraphState(graph: GraphState): void
  flushNow(): Promise<AcceptedGraphSnapshot | null>
  resolveConflictKeepingLocal(): Promise<AcceptedGraphSnapshot | null>
  resolveConflictUsingRemote(): Promise<AcceptedGraphSnapshot | null>
  validationResult: Ref<ValidationResult | null>
  isPending: Ref<boolean>
  syncState: Ref<SyncState>
  lastError: Readonly<Ref<unknown | null>>
  currentGraph: Ref<GraphState>
  dispose(): void
}

function deepCloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

/**
 * Serialise a Vue Flow node object into the backend NodeState format.
 */
function serializeNode(n: any): NodeState {
  const data = n.data ?? {}
  const common = {
    id: n.id,
    name: data.name ?? n.id,
    position: [n.position?.x ?? 0, n.position?.y ?? 0] as [number, number],
    resources: data.resources ?? {},
    enabled: data.enabled ?? true,
    collapsed: data.collapsed ?? false,
  }
  // `data.nodeType` is the platform discriminator. Vue Flow owns the top-level
  // `type` as a renderer key and can temporarily omit it while normalising a
  // newly inserted node. Serialisation must not fail in that window: an
  // exception from an `onConnect` listener also prevents Vue Flow from ending
  // the pointer gesture, leaving its connection line attached to the cursor.
  if (data.nodeType === 'workflow') {
    return {
      type: 'workflow',
      ...common,
      workflow: deepCloneJson(data.workflow),
      bindings: deepCloneJson(data.bindings ?? {}),
      source: data.source == null ? null : deepCloneJson(data.source),
    }
  }
  if (data.nodeType !== 'tool') {
    throw new Error(`Canvas node ${n.id} has no valid discriminator`)
  }
  return {
    type: 'tool',
    ...common,
    tool_name: data.toolName,
    parameters: deepCloneJson(data.parameters ?? {}),
    output_templates: deepCloneJson(data.output_templates ?? {}),
    tool_module: data.toolModule ?? null,
    tool_class: data.toolClass ?? null,
    tool_package: data.toolPackage ?? null,
    tool_package_version: data.toolPackageVersion ?? null,
    source_module: data.sourceModule ?? null,
  }
}

/**
 * Serialise a Vue Flow edge object into the backend Edge format
 * (either ColumnEdge or DataFrameEdge).
 */
function serializeEdge(e: any): Edge {
  const source = decodeEndpointHandle(e.sourceHandle ?? '')
  const target = decodeEndpointHandle(e.targetHandle ?? '')
  if (e.type === 'dataframe') {
    if (source.kind !== 'dataframe-output') {
      throw new Error(`DataFrame edge ${e.id} has a non-DataFrame source`)
    }
    if (target.kind !== 'dataframe-position' && target.kind !== 'workflow-input') {
      throw new Error(`DataFrame edge ${e.id} has an incompatible target`)
    }
    return {
      type: 'dataframe',
      id: e.id,
      source_node: e.source,
      target_node: e.target,
      target_position: target.kind === 'dataframe-position' ? target.index : null,
      target_input: target.kind === 'workflow-input' ? target.id : null,
    }
  }
  if (e.type !== 'column') throw new Error(`Unknown canvas edge type: ${e.type}`)
  if (source.kind !== 'tool-output' && source.kind !== 'workflow-output') {
    throw new Error(`Column edge ${e.id} has an incompatible source`)
  }
  if (target.kind !== 'tool-input' && target.kind !== 'workflow-input') {
    throw new Error(`Column edge ${e.id} has an incompatible target`)
  }
  return {
    type: 'column',
    id: e.id,
    source_node: e.source,
    target_node: e.target,
    source_output: source.kind === 'workflow-output' ? source.id : source.name,
    target_input: target.kind === 'workflow-input' ? target.id : target.name,
  }
}

/**
 * Convert raw Vue Flow state ({ nodes, edges }) into the backend GraphState.
 */
export function serializeGraph(raw: {
  nodes: any[]
  edges: any[]
  schema_version?: 1
  name?: string
  display_name?: string
  interface?: GraphState['interface']
  config?: GraphState['config']
}): GraphState {
  return {
    schema_version: raw.schema_version ?? 1,
    name: raw.name ?? 'workflow',
    display_name: raw.display_name ?? raw.name ?? 'Workflow',
    nodes: raw.nodes.map(serializeNode),
    edges: raw.edges.map(serializeEdge),
    interface: deepCloneJson(raw.interface ?? { inputs: [], outputs: [] }),
    config: deepCloneJson(raw.config ?? {
      storage_path: './bif_data',
      engine: 'wetlands',
      execution: 'parallel',
    }),
  }
}

export const graphSyncCanvasSessions = canvasSessionRegistry
export const NESTED_SNAPSHOT_PERSISTENCE_RESOURCE = 'nested-snapshot-persistence'

interface NestedSnapshotPersistenceLease {
  readonly resource: NestedSnapshotPersistence
  dispose(): void
}

const retainedNestedSnapshotResources = new Map<string, NestedSnapshotPersistence>()

// Shell panels use this state-free adapter to follow Dockview activation.
// It delegates exclusively to a registered canvas resource.
let activeFacade: GraphSyncApi | null = null

export function useGraphSync(options: CanvasScopedGraphSyncOptions): GraphSyncApi
export function useGraphSync(): GraphSyncApi
export function useGraphSync(options?: CanvasScopedGraphSyncOptions): GraphSyncApi {
  if (options) return registerScopedGraphSync(options)
  if (activeFacade === null) activeFacade = createActiveFacade()
  return activeFacade
}

/** Activate only from an explicit Dockview canvas-panel activation event. */
export function activateGraphSyncCanvas(canvasId: CanvasId): boolean {
  if (graphSyncCanvasSessions.get(canvasId) === null) return false
  graphSyncCanvasSessions.activate(canvasId)
  return true
}

export function unregisterGraphSyncCanvas(canvasId: CanvasId): void {
  graphSyncCanvasSessions.unregister(canvasId)
}

/** Test-only: reset scoped resources and the state-free active adapter. */
export function _resetGraphSyncForTest(): void {
  graphSyncCanvasSessions.dispose()
  for (const resource of retainedNestedSnapshotResources.values()) {
    resource.dispose()
  }
  retainedNestedSnapshotResources.clear()
  activeFacade = null
}

function registerScopedGraphSync(options: CanvasScopedGraphSyncOptions): GraphSyncApi {
  graphSyncCanvasSessions.register(options.descriptor)
  if (options.descriptor.kind === 'root') {
    const resource = getOrCreateRootPersistenceResource({
      descriptor: options.descriptor,
      getWorkflowId: options.getWorkflowId,
    })
    graphSyncCanvasSessions.getOrCreateCoordinator(
      options.descriptor.canvasId,
      () => resource,
    )
    return createRootBoundApi(resource, () => {
      unregisterGraphSyncCanvas(options.descriptor.canvasId)
    })
  }
  if (options.nestedSnapshot) {
    const sessionId = options.nestedSnapshot.initialSnapshot.session_id
    let resource = retainedNestedSnapshotResources.get(sessionId)
    if (!resource) {
      resource = createNestedSnapshotPersistence({
        canvasId: options.descriptor.canvasId,
        initialSnapshot: options.nestedSnapshot.initialSnapshot,
        onAccepted: options.nestedSnapshot.onAccepted,
      })
      retainedNestedSnapshotResources.set(sessionId, resource)
    }
    const lease = graphSyncCanvasSessions.getOrCreateResource(
      options.descriptor.canvasId,
      NESTED_SNAPSHOT_PERSISTENCE_RESOURCE,
      () => ({ resource, dispose: () => {} }),
    ) as NestedSnapshotPersistenceLease
    graphSyncCanvasSessions.getOrCreateCoordinator(
      options.descriptor.canvasId,
      () => ({ ...lease.resource.coordinator, dispose: () => {} }),
    )
    return createNestedBoundApi(lease.resource, () => {
      unregisterGraphSyncCanvas(options.descriptor.canvasId)
    })
  }
  throw new Error('Nested graph sync requires an accepted durable snapshot')
}

export async function deleteRetainedNestedSnapshot(
  sessionId: string,
): Promise<boolean> {
  const resource = retainedNestedSnapshotResources.get(sessionId)
  if (!resource) return false
  await resource.deleteLatest()
  forgetRetainedNestedSnapshot(sessionId)
  return true
}

/** Forget a server-deleted snapshot without issuing another DELETE request. */
export function forgetRetainedNestedSnapshot(sessionId: string): boolean {
  const resource = retainedNestedSnapshotResources.get(sessionId)
  if (!resource) return false
  resource.dispose()
  retainedNestedSnapshotResources.delete(sessionId)
  return true
}

/** Flush the durable retained writer before a parent workflow mutation. */
export async function flushRetainedNestedSnapshot(sessionId: string): Promise<void> {
  const resource = retainedNestedSnapshotResources.get(sessionId)
  if (!resource) return
  await resource.flushLatest()
}

function createNestedBoundApi(
  resource: NestedSnapshotPersistence,
  dispose: () => void,
): GraphSyncApi {
  function queueGraph(graph: GraphState, force = false): void {
    if (
      !force
      && resource.coordinator.semanticRevision.value === 0
      && graphDocumentsEqual(resource.currentGraph.value, graph)
    ) {
      return
    }
    resource.queue(graph)
  }

  return {
    syncGraph: graph => queueGraph(serializeGraph(graph)),
    syncGraphState: graph => queueGraph(graph),
    revalidateGraphState: graph => queueGraph(graph, true),
    flushNow: async () => {
      await nextTick()
      return resource.flushLatest()
    },
    resolveConflictKeepingLocal: async () => {
      await nextTick()
      return resource.resolveConflictKeepingLocal()
    },
    resolveConflictUsingRemote: async () => {
      await nextTick()
      return resource.resolveConflictUsingRemote()
    },
    validationResult: resource.validationResult,
    isPending: resource.coordinator.isPending,
    syncState: resource.coordinator.syncState,
    lastError: resource.coordinator.lastError,
    currentGraph: resource.currentGraph,
    dispose,
  }
}

function createRootBoundApi(
  resource: RootCanvasPersistenceResource,
  dispose: () => void,
): GraphSyncApi {
  const lastError = computed<unknown | null>(() => {
    const issue = resource.persistenceIssue.value
    if (
      resource.validationSyncState.value !== 'error'
      || issue?.kind !== 'error'
      || issue.source !== 'draft'
    ) return null
    return issue
  })

  function syncGraphState(graph: GraphState): void {
    resource.queueValidation(graph)
  }

  return {
    syncGraph: graph => resource.queueValidation(serializeGraph(graph)),
    syncGraphState,
    revalidateGraphState: graph => resource.queueValidation(graph, { force: true }),
    flushNow: async () => {
      await nextTick()
      await resource.flushValidation()
      const validation = resource.validationResult.value
      if (!validation) return null
      return {
        graph: deepCloneJson(resource.currentGraph.value),
        validation: deepCloneJson(validation),
        snapshotRevision: null,
      }
    },
    resolveConflictKeepingLocal: async () => null,
    resolveConflictUsingRemote: async () => null,
    validationResult: resource.validationResult,
    isPending: resource.isValidationPending,
    syncState: resource.validationSyncState,
    lastError,
    currentGraph: resource.currentGraph,
    dispose,
  }
}

function createActiveFacade(): GraphSyncApi {
  const selected = (): GraphSyncApi | null => {
    const canvasId = graphSyncCanvasSessions.activeCanvasId.value
    if (canvasId !== null) {
      const session = graphSyncCanvasSessions.get(canvasId)
      if (session?.descriptor.kind === 'root') {
        const resource = graphSyncCanvasSessions.getResource<RootCanvasPersistenceResource>(
          canvasId,
          ROOT_PERSISTENCE_RESOURCE,
        )
        if (resource) {
          return createRootBoundApi(resource, () => {
            unregisterGraphSyncCanvas(canvasId)
          })
        }
      }
      const nestedLease = graphSyncCanvasSessions.getResource<NestedSnapshotPersistenceLease>(
        canvasId,
        NESTED_SNAPSHOT_PERSISTENCE_RESOURCE,
      )
      if (nestedLease) {
        return createNestedBoundApi(nestedLease.resource, () => {
          unregisterGraphSyncCanvas(canvasId)
        })
      }
    }
    return null
  }
  const required = (): GraphSyncApi => {
    const target = selected()
    if (target === null) throw new Error('No active canvas graph sync session')
    return target
  }
  const fallbackGraph = emptyGraph()

  return {
    syncGraph: graph => required().syncGraph(graph),
    syncGraphState: graph => required().syncGraphState(graph),
    revalidateGraphState: graph => required().revalidateGraphState(graph),
    flushNow: () => required().flushNow(),
    resolveConflictKeepingLocal: () => required().resolveConflictKeepingLocal(),
    resolveConflictUsingRemote: () => required().resolveConflictUsingRemote(),
    validationResult: computed({
      get: () => selected()?.validationResult.value ?? null,
      set: value => { required().validationResult.value = value },
    }),
    isPending: computed({
      get: () => selected()?.isPending.value ?? false,
      set: value => { required().isPending.value = value },
    }),
    syncState: computed({
      get: () => selected()?.syncState.value ?? 'idle',
      set: value => { required().syncState.value = value },
    }),
    lastError: computed(() => selected()?.lastError.value ?? null),
    currentGraph: computed({
      get: () => selected()?.currentGraph.value ?? fallbackGraph,
      set: value => { required().currentGraph.value = value },
    }),
    dispose: () => required().dispose(),
  }
}
