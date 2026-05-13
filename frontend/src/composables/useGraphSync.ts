import { computed, ref, type Ref } from 'vue'
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

export interface UseGraphSyncOptions {
  draftId?: string | null
  initialRevision?: number | null
  initialGraph?: GraphState | null
}

export interface GraphDraftSync {
  syncGraph: (graph: { nodes: any[]; edges: any[] }) => void
  flushNow: () => Promise<void>
  patchParameters: (
    nodeId: string,
    toolName: string,
    parameters: Record<string, unknown>,
  ) => Promise<void>
  validationResult: Ref<ValidationResult | null>
  isPending: Ref<boolean>
  syncState: Ref<SyncState>
  currentGraph: Ref<GraphState>
  draft_id: Ref<string | null>
  revision: Ref<number>
  client_seq: Ref<number>
  graph: Ref<GraphState>
  validation_result: Ref<ValidationResult | null>
  dirty: Ref<boolean>
  pending_sync: Ref<boolean>
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

const LEGACY_DRAFT_KEY = '__legacy__'

// Module-level registry keyed by draft id. Canvas callers pass a draft id and
// get isolated validation/debounce/revision state; shell-level callers without
// a draft id read the currently active draft via a small facade so legacy
// consumers keep working during backend integration.
let _instances = new Map<string, GraphDraftSync>()
const _activeDraftKey = ref(LEGACY_DRAFT_KEY)
let _activeFacade: GraphDraftSync | null = null

export function useGraphSync(options: UseGraphSyncOptions = {}): GraphDraftSync {
  if (options.draftId !== undefined && options.draftId !== null) {
    const key = options.draftId
    const existing = _instances.get(key)
    if (existing) {
      _activeDraftKey.value = key
      return existing
    }
    const created = _createGraphSync({
      draftId: key,
      initialRevision: options.initialRevision,
      initialGraph: options.initialGraph,
    })
    _instances.set(key, created)
    _activeDraftKey.value = key
    return created
  }
  if (_activeFacade === null) {
    _activeFacade = _createActiveGraphSyncFacade()
  }
  ensureLegacyGraphSync()
  return _activeFacade
}

/** Test-only: reset the singleton so each test starts clean. */
export function _resetGraphSyncForTest(): void {
  _instances = new Map<string, GraphDraftSync>()
  _activeDraftKey.value = LEGACY_DRAFT_KEY
  _activeFacade = null
}

function ensureLegacyGraphSync(): GraphDraftSync {
  let instance = _instances.get(LEGACY_DRAFT_KEY)
  if (!instance) {
    instance = _createGraphSync({ draftId: null })
    _instances.set(LEGACY_DRAFT_KEY, instance)
  }
  return instance
}

function activeGraphSync(): GraphDraftSync {
  return _instances.get(_activeDraftKey.value) ?? ensureLegacyGraphSync()
}

function _createActiveGraphSyncFacade(): GraphDraftSync {
  return {
    syncGraph: (graph) => ensureLegacyGraphSync().syncGraph(graph),
    flushNow: () => activeGraphSync().flushNow(),
    patchParameters: (nodeId, toolName, parameters) =>
      activeGraphSync().patchParameters(nodeId, toolName, parameters),
    validationResult: computed(() => activeGraphSync().validationResult.value),
    isPending: computed(() => activeGraphSync().isPending.value),
    syncState: computed(() => activeGraphSync().syncState.value),
    currentGraph: computed(() => activeGraphSync().currentGraph.value),
    draft_id: computed(() => activeGraphSync().draft_id.value),
    revision: computed(() => activeGraphSync().revision.value),
    client_seq: computed(() => activeGraphSync().client_seq.value),
    graph: computed(() => activeGraphSync().graph.value),
    validation_result: computed(() => activeGraphSync().validation_result.value),
    dirty: computed(() => activeGraphSync().dirty.value),
    pending_sync: computed(() => activeGraphSync().pending_sync.value),
  } as GraphDraftSync
}

function _createGraphSync(options: {
  draftId?: string | null
  initialRevision?: number | null
  initialGraph?: GraphState | null
}): GraphDraftSync {
  const validationResult = ref<ValidationResult | null>(null)
  const isPending = ref(false)
  const syncState = ref<SyncState>('idle')
  // Latest graph seen by syncGraph/flushNow. Read by consumers (e.g. the
  // Run button) that need the current graph without owning a Vue Flow
  // instance.
  const currentGraph = ref<GraphState>(deepCloneJson(
    options.initialGraph ?? { nodes: [], edges: [] },
  ))
  const draft_id = ref<string | null>(options.draftId ?? null)
  const revision = ref(options.initialRevision ?? 0)
  const client_seq = ref(0)
  const graph = currentGraph
  const validation_result = validationResult
  const dirty = ref(false)
  const pending_sync = ref(false)

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
    dirty.value = true
    pending_sync.value = true
    if (draft_id.value) {
      _activeDraftKey.value = draft_id.value
    }
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
    currentGraph.value = graph
    const baseRevision = revision.value
    const nextClientSeq = client_seq.value + 1
    client_seq.value = nextClientSeq

    try {
      const response = draft_id.value
        ? await api.put(
          `/api/v1/workflow-drafts/${encodeURIComponent(draft_id.value)}`,
          {
            graph,
            base_revision: baseRevision,
            client_seq: nextClientSeq,
          },
          { signal: controller.signal },
        )
        : await api.put(
          '/api/v1/graph',
          {
            graph,
            workflow_name: useWorkflowStore().currentName ?? null,
          },
          { signal: controller.signal },
        )
      // Only apply if this is still the latest request
      if (thisId === requestId) {
        const data = response.data as {
          draft_id?: string
          revision?: number
          validation?: ValidationResult
          validation_result?: ValidationResult
        } | ValidationResult
        if ('draft_id' in data && data.draft_id !== undefined) {
          draft_id.value = data.draft_id
        }
        if ('revision' in data && typeof data.revision === 'number') {
          revision.value = data.revision
        }
        validationResult.value =
          'validation' in data && data.validation
            ? data.validation
            : 'validation_result' in data && data.validation_result
              ? data.validation_result
              : data as ValidationResult
        dirty.value = false
        pending_sync.value = false
        syncState.value = 'idle'
      }
    } catch (err: any) {
      // Ignore aborts from a newer request.
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') {
        return
      }
      if (thisId === requestId) {
        syncState.value = 'error'
        pending_sync.value = false
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
      const response = draft_id.value
        ? await api.patch(
          `/api/v1/workflow-drafts/${encodeURIComponent(draft_id.value)}/nodes/${nodeId}/parameters`,
          {
            parameters,
            base_revision: revision.value,
            client_seq: client_seq.value + 1,
          },
        )
        : await api.patch(
          `/api/v1/graph/nodes/${nodeId}/parameters`,
          { parameters },
          { params: { tool_name: toolName } },
        )
      const data = response.data as {
        revision?: number
        validation?: ValidationResult
      } | ValidationResult | undefined
      if (data && 'revision' in data && typeof data.revision === 'number') {
        revision.value = data.revision
        client_seq.value += 1
      }
      const patch = data && 'validation' in data && data.validation
        ? data.validation
        : data as ValidationResult | undefined
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
    draft_id,
    revision,
    client_seq,
    graph,
    validation_result,
    dirty,
    pending_sync,
  }
}
