import { ref } from 'vue'
import { api } from '@/api/client'
import { useErrorReporting } from '@/composables/useErrorReporting'
import { useWorkflowStore } from '@/stores/workflow'
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

export type SyncState = 'idle' | 'pending' | 'error'

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

// Module-level singleton so multiple callers (CanvasView, MenuBar, run
// button) observe the same validation result, debounce timer, and latest
// graph ref. Tests reset via _resetGraphSyncForTest and mock the
// useErrorReporting module to observe error reporting.
let _instance: ReturnType<typeof _createGraphSync> | null = null

export function useGraphSync() {
  if (_instance !== null) return _instance
  _instance = _createGraphSync()
  return _instance
}

/** Test-only: reset the singleton so each test starts clean. */
export function _resetGraphSyncForTest(): void {
  _instance = null
}

function _createGraphSync() {
  const validationResult = ref<ValidationResult | null>(null)
  const isPending = ref(false)
  const syncState = ref<SyncState>('idle')
  // Latest graph seen by syncGraph/flushNow. Read by consumers (e.g. the
  // Run button) that need the current graph without owning a Vue Flow
  // instance.
  const currentGraph = ref<GraphState>({ nodes: [], edges: [] })

  let timer: ReturnType<typeof setTimeout> | null = null
  let pendingGraph: { nodes: any[]; edges: any[] } | null = null
  let requestId = 0
  let inflightController: AbortController | null = null

  function _reportError(status: number | undefined, detail: string): void {
    // useErrorReporting requires an active Pinia. Tests that don't set one
    // up never trigger this path (they don't reject the api mock); a real
    // failure here would be a misconfiguration worth surfacing.
    try {
      const { reportError } = useErrorReporting()
      reportError({ kind: 'graph_sync_error', status, detail })
    } catch (e) {
      console.warn('[graph-sync] failed to report error:', e)
    }
  }

  function syncGraph(graph: { nodes: any[]; edges: any[] }): void {
    pendingGraph = graph
    currentGraph.value = serializeGraph(graph)
    if (timer !== null) {
      clearTimeout(timer)
    }
    timer = setTimeout(() => {
      sendNow()
    }, 300)
  }

  async function sendNow(): Promise<void> {
    if (pendingGraph === null) return
    const raw = pendingGraph
    pendingGraph = null
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }

    // Cancel any in-flight request.
    if (inflightController !== null) {
      inflightController.abort()
    }
    const controller = new AbortController()
    inflightController = controller

    const thisId = ++requestId
    isPending.value = true
    syncState.value = 'pending'

    const graph = serializeGraph(raw)

    try {
      const workflowName = useWorkflowStore().currentName
      const response = await api.put(
        '/api/v1/graph',
        { graph, workflow_name: workflowName ?? null },
        { signal: controller.signal },
      )
      // Only apply if this is still the latest request
      if (thisId === requestId) {
        validationResult.value = response.data
        syncState.value = 'idle'
      }
    } catch (err: any) {
      // Ignore aborts from a newer request.
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') {
        return
      }
      if (thisId === requestId) {
        syncState.value = 'error'
        _reportError(err?.response?.status, err?.message ?? 'PUT /graph failed')
      }
    } finally {
      if (thisId === requestId) {
        isPending.value = false
        if (inflightController === controller) {
          inflightController = null
        }
      }
    }
  }

  async function flushNow(): Promise<void> {
    await sendNow()
  }

  async function patchParameters(
    nodeId: string,
    toolName: string,
    parameters: Record<string, unknown>,
  ): Promise<void> {
    syncState.value = 'pending'
    try {
      const response = await api.patch(
        `/api/v1/graph/nodes/${nodeId}/parameters`,
        { parameters },
        { params: { tool_name: toolName } },
      )
      const patch = response.data as ValidationResult | undefined
      if (patch) {
        // Merge: update only the patched node's entry; replace the errors
        // list with the server response's errors scoped to that node.
        const prev = validationResult.value
        const mergedStatuses = {
          ...(prev?.node_statuses ?? {}),
          ...(patch.node_statuses ?? {}),
        }
        const otherErrors = (prev?.errors ?? []).filter(
          (e) => e.node !== nodeId,
        )
        validationResult.value = {
          valid:
            (patch.valid ?? true) &&
            (prev?.valid ?? true) &&
            otherErrors.length === 0,
          node_statuses: mergedStatuses,
          errors: [...otherErrors, ...(patch.errors ?? [])],
        }
      }
      syncState.value = 'idle'
    } catch (err: any) {
      syncState.value = 'error'
      _reportError(
        err?.response?.status,
        err?.message ?? 'PATCH /graph failed',
      )
    }
    // Always trigger a debounced PUT /graph follow-up to refresh the full
    // graph's statuses. The caller is responsible for supplying the current
    // graph to `syncGraph`; we schedule here only if there's a pending graph
    // from the caller. This keeps the PATCH fast pre-flight / PUT authoritative
    // split clean.
  }

  return {
    syncGraph,
    flushNow,
    patchParameters,
    validationResult,
    isPending,
    syncState,
    currentGraph,
  }
}
