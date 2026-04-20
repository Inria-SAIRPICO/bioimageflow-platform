import { ref } from 'vue'
import { api } from '@/api/client'
import { useIndexedDB } from '@/composables/useIndexedDB'
import type {
  GraphState,
  NodeState,
  Edge,
  ValidationResult,
} from '@/api/types'

/**
 * Serialise a Vue Flow node object into the backend NodeState format.
 */
function serializeNode(n: any): NodeState {
  return {
    id: n.id,
    name: n.data?.name ?? n.id,
    tool_name: n.data?.toolName ?? '',
    position: [n.position?.x ?? 0, n.position?.y ?? 0],
    parameters: n.data?.parameters ?? {},
    output_templates: n.data?.output_templates ?? {},
    enabled: n.data?.enabled ?? true,
    collapsed: n.data?.collapsed ?? false,
  }
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
}): GraphState {
  return {
    nodes: raw.nodes.map(serializeNode),
    edges: raw.edges.map(serializeEdge),
  }
}

export function useGraphSync() {
  const validationResult = ref<ValidationResult | null>(null)
  const isPending = ref(false)
  const { saveWorkflow, loadWorkflow } = useIndexedDB()

  let timer: ReturnType<typeof setTimeout> | null = null
  let pendingGraph: { nodes: any[]; edges: any[] } | null = null
  let requestId = 0

  function syncGraph(graph: { nodes: any[]; edges: any[] }): void {
    pendingGraph = graph
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

    // Save raw Vue Flow state to IndexedDB (fire-and-forget)
    saveWorkflow({ nodes: raw.nodes, edges: raw.edges })

    const thisId = ++requestId
    isPending.value = true

    const graph = serializeGraph(raw)

    try {
      const response = await api.put('/api/v1/graph', graph)
      // Only apply if this is still the latest request
      if (thisId === requestId) {
        validationResult.value = response.data
      }
    } finally {
      if (thisId === requestId) {
        isPending.value = false
      }
    }
  }

  async function flushNow(): Promise<void> {
    await sendNow()
  }

  async function patchParameters(
    nodeId: string,
    parameters: Record<string, unknown>,
  ): Promise<void> {
    await api.patch(`/api/v1/graph/nodes/${nodeId}/parameters`, parameters)
  }

  return { syncGraph, flushNow, patchParameters, loadWorkflow, validationResult, isPending }
}
