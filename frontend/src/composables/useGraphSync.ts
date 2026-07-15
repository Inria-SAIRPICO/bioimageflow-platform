import { computed, nextTick, type Ref } from 'vue'
import { api } from '@/api/client'
import { useErrorReporting } from '@/composables/useErrorReporting'
import { useWorkflowStore } from '@/stores/workflow'
import {
  CanvasSessionRegistry,
  canvasIdFromPanelId,
  type CanvasId,
  type CanvasSessionDescriptor,
} from '@/sessions/canvasSessionRegistry'
import {
  createGraphSyncCoordinator,
  type GraphSyncCoordinator,
  type SyncState,
} from '@/sessions/graphSyncCoordinator'
import type {
  ColumnRefEdge,
  GraphState,
  NodeState,
  PositionalEdge,
  PublishedInput,
  PublishedOutput,
  ValidationResult,
} from '@/api/types'

type Edge = ColumnRefEdge | PositionalEdge

export type { SyncState } from '@/sessions/graphSyncCoordinator'

export interface CanvasScopedGraphSyncOptions {
  descriptor: CanvasSessionDescriptor
  getWorkflowId: () => string | null
}

export interface GraphSyncApi {
  syncGraph(graph: Parameters<typeof serializeGraph>[0]): void
  syncGraphState(graph: GraphState): void
  syncNodeParameters(nodeId: string, parameters: Record<string, unknown>): void
  flushNow(): Promise<void>
  validationResult: Ref<ValidationResult | null>
  isPending: Ref<boolean>
  syncState: Ref<SyncState>
  currentGraph: Ref<GraphState>
  dispose(): void
}

function deepCloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function hasSubWorkflowFields(data: Record<string, any> | undefined): boolean {
  if (!data) return false
  return data.toolName === '__sub_workflow__'
    || (data.sub_workflow !== undefined && data.sub_workflow !== null)
    || (Array.isArray(data.published_inputs) && data.published_inputs.length > 0)
    || (Array.isArray(data.published_outputs) && data.published_outputs.length > 0)
    || typeof data.source_workflow_name === 'string'
    || (
      data.sub_workflow_readonly_reason !== undefined
      && data.sub_workflow_readonly_reason !== null
    )
}

/**
 * Serialise a Vue Flow node object into the backend NodeState format.
 */
function serializeNode(n: any): NodeState {
  const data = n.data ?? {}
  const node = {
    id: n.id,
    name: data.name ?? n.id,
    tool_name: data.toolName ?? '',
    position: [n.position?.x ?? 0, n.position?.y ?? 0],
    parameters: data.parameters ?? {},
    resources: data.resources ?? {},
    output_templates: data.output_templates ?? {},
    enabled: data.enabled ?? true,
    collapsed: data.collapsed ?? false,
  } as NodeState & Record<string, unknown>
  if (hasSubWorkflowFields(data)) {
    for (const key of [
      'sub_workflow',
      'published_inputs',
      'published_outputs',
      'sub_workflow_readonly_reason',
      'source_workflow_name',
    ]) {
      if (data[key] !== undefined) {
        node[key] = deepCloneJson(data[key])
      }
    }
  }
  return node as NodeState
}

/**
 * Serialise a Vue Flow edge object into the backend Edge format
 * (either ColumnRefEdge or PositionalEdge).
 */
function serializeEdge(e: any): Edge {
  if (e.type === 'positional') {
    const handle = e.targetHandle ?? ''
    const idx = parseInt(handle.replace('__positional_', ''), 10)
    return {
      type: 'positional',
      id: e.id,
      source_node: e.source,
      target_node: e.target,
      positional_index: isNaN(idx) ? 0 : idx,
    }
  }
  return {
    type: 'column_ref',
    id: e.id,
    source_node: e.source,
    target_node: e.target,
    source_output: e.sourceHandle ?? '',
    target_input: e.targetHandle ?? '',
  }
}

/**
 * Convert raw Vue Flow state ({ nodes, edges }) into the backend GraphState.
 */
export function serializeGraph(raw: {
  nodes: any[]
  edges: any[]
  published_inputs?: PublishedInput[]
  published_outputs?: PublishedOutput[]
}): GraphState {
  const graph = {
    nodes: raw.nodes.map(serializeNode),
    edges: raw.edges.map(serializeEdge),
  } as GraphState
  if (raw.published_inputs !== undefined) {
    graph.published_inputs = deepCloneJson(raw.published_inputs)
  }
  if (raw.published_outputs !== undefined) {
    graph.published_outputs = deepCloneJson(raw.published_outputs)
  }
  return graph
}

export const graphSyncCanvasSessions = new CanvasSessionRegistry()

let legacyInstance: GraphSyncApi | null = null
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

/** Test-only: reset all scoped and compatibility state. */
export function _resetGraphSyncForTest(): void {
  graphSyncCanvasSessions.dispose()
  legacyInstance?.dispose()
  legacyInstance = null
  activeFacade = null
}

function registerScopedGraphSync(options: CanvasScopedGraphSyncOptions): GraphSyncApi {
  graphSyncCanvasSessions.register(options.descriptor)
  const coordinator = graphSyncCanvasSessions.getOrCreateCoordinator(
    options.descriptor.canvasId,
    descriptor => createCoordinator(
      descriptor.canvasId,
      descriptor.kind === 'root' ? descriptor.workflowId : options.getWorkflowId(),
      options.getWorkflowId,
    ),
  )
  return createBoundApi(coordinator, () => {
    unregisterGraphSyncCanvas(options.descriptor.canvasId)
  })
}

function createCoordinator(
  canvasId: CanvasId,
  workflowId: string | null,
  getWorkflowId?: () => string | null,
): GraphSyncCoordinator {
  return createGraphSyncCoordinator({
    canvasId,
    workflowId,
    getWorkflowId,
    transport: async ({ graph, workflowId: queuedWorkflowId, signal }) => {
      const response = await api.put<ValidationResult>(
        '/api/v1/graph',
        { graph, workflow_name: queuedWorkflowId },
        { signal },
      )
      return response.data
    },
    onOperationalError: (error) => {
      const err = error as {
        message?: string
        response?: { status?: number }
      }
      reportGraphSyncError(
        err.response?.status,
        err.message ?? 'PUT /graph failed',
      )
    },
  })
}

function createBoundApi(
  coordinator: GraphSyncCoordinator,
  dispose: () => void,
): GraphSyncApi {
  function syncGraph(graph: Parameters<typeof serializeGraph>[0]): void {
    coordinator.queue(serializeGraph(graph))
  }

  function syncGraphState(graph: GraphState): void {
    coordinator.queue(graph)
  }

  function syncNodeParameters(
    nodeId: string,
    parameters: Record<string, unknown>,
  ): void {
    const graph = deepCloneJson(coordinator.currentGraph.value)
    const node = graph.nodes.find(candidate => candidate.id === nodeId)
    if (!node) return
    node.parameters = deepCloneJson(parameters)
    syncGraphState(graph)
  }

  async function flushNow(): Promise<void> {
    await nextTick()
    await coordinator.flushLatest()
  }

  return {
    syncGraph,
    syncGraphState,
    syncNodeParameters,
    flushNow,
    validationResult: coordinator.validationResult,
    isPending: coordinator.isPending,
    syncState: coordinator.syncState,
    currentGraph: coordinator.currentGraph,
    dispose,
  }
}

function createActiveFacade(): GraphSyncApi {
  const selected = (): GraphSyncApi | null => {
    const canvasId = graphSyncCanvasSessions.activeCanvasId.value
    if (canvasId !== null) {
      const coordinator = graphSyncCanvasSessions.get(canvasId)?.coordinator
      if (coordinator) {
        return createBoundApi(coordinator as GraphSyncCoordinator, () => {
          unregisterGraphSyncCanvas(canvasId)
        })
      }
    }
    if (graphSyncCanvasSessions.sessionCount.value === 0) {
      return getLegacyInstance()
    }
    return null
  }
  const required = (): GraphSyncApi => {
    const target = selected()
    if (target === null) throw new Error('No active canvas graph sync session')
    return target
  }
  const emptyGraph: GraphState = { nodes: [], edges: [] }

  return {
    syncGraph: graph => required().syncGraph(graph),
    syncGraphState: graph => required().syncGraphState(graph),
    syncNodeParameters: (nodeId, parameters) => {
      required().syncNodeParameters(nodeId, parameters)
    },
    flushNow: () => required().flushNow(),
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
    currentGraph: computed({
      get: () => selected()?.currentGraph.value ?? emptyGraph,
      set: value => { required().currentGraph.value = value },
    }),
    dispose: () => required().dispose(),
  }
}

function getLegacyInstance(): GraphSyncApi {
  if (legacyInstance !== null) return legacyInstance
  const coordinator = createCoordinator(
    canvasIdFromPanelId('legacy:canvas'),
    null,
    () => {
      try {
        return useWorkflowStore().currentName
      } catch {
        return null
      }
    },
  )
  legacyInstance = createBoundApi(coordinator, coordinator.dispose)
  return legacyInstance
}

function reportGraphSyncError(status: number | undefined, detail: string): void {
  try {
    const { reportError } = useErrorReporting()
    reportError({ kind: 'graph_sync_error', status, detail })
  } catch (error) {
    console.warn('[graph-sync] failed to report error:', error)
  }
}
