import { reactive } from 'vue'
import { defineStore } from 'pinia'
import { fetchNodeOutputSchema } from '@/api/client'
import { serializeGraph } from '@/composables/useGraphSync'
import type { NodeOutputSchemaResponse, ToolMetadata } from '@/api/types'

export const useResolvedOutputsStore = defineStore('resolvedOutputs', () => {
  const resolvedOutputsByNodeId = reactive<Record<string, NodeOutputSchemaResponse>>({})

  // Per-node debounce timers keyed by nodeId.
  const _timers: Record<string, ReturnType<typeof setTimeout>> = {}

  /**
   * Refresh the resolved output schema for a single node, debounced.
   * After refreshing, walk downstream along positional edges and refresh
   * any visited node that also has `dynamic_outputs === true`.
   */
  function refreshResolvedOutputs(
    nodeId: string,
    getGraph: () => { nodes: any[]; edges: any[] },
    getToolForNode: (nodeId: string) => ToolMetadata | undefined,
  ): void {
    if (_timers[nodeId]) {
      clearTimeout(_timers[nodeId])
    }
    _timers[nodeId] = setTimeout(async () => {
      delete _timers[nodeId]
      const raw = getGraph()
      const graph = serializeGraph(raw)

      try {
        const result = await fetchNodeOutputSchema(nodeId, graph)
        resolvedOutputsByNodeId[nodeId] = result
      } catch {
        resolvedOutputsByNodeId[nodeId] = { resolved: false, columns: {} }
      }

      // Walk downstream along positional edges and refresh any dynamic_outputs node.
      _propagateDownstream(nodeId, raw, graph, getToolForNode)
    }, 200)
  }

  /**
   * Walk downstream from `startNodeId` along positional edges.
   * For each visited node whose tool has `dynamic_outputs === true`,
   * refresh its resolved outputs.
   */
  async function _propagateDownstream(
    startNodeId: string,
    raw: { nodes: any[]; edges: any[] },
    graph: ReturnType<typeof serializeGraph>,
    getToolForNode: (nodeId: string) => ToolMetadata | undefined,
  ): Promise<void> {
    const visited = new Set<string>()
    const queue = [startNodeId]

    while (queue.length > 0) {
      const current = queue.shift()!
      if (visited.has(current)) continue
      visited.add(current)

      // Find downstream nodes connected via positional edges from `current`.
      for (const edge of raw.edges) {
        if (edge.source !== current) continue
        const targetHandle = edge.targetHandle ?? ''
        if (!targetHandle.startsWith('__positional_')) continue
        const targetId = edge.target
        if (visited.has(targetId)) continue

        const targetTool = getToolForNode(targetId)
        if (targetTool?.dynamic_outputs === true) {
          try {
            const result = await fetchNodeOutputSchema(targetId, graph)
            resolvedOutputsByNodeId[targetId] = result
          } catch {
            resolvedOutputsByNodeId[targetId] = { resolved: false, columns: {} }
          }
          // Continue propagating from this node too.
          queue.push(targetId)
        }
      }
    }
  }

  /**
   * Immediate (non-debounced) refresh. Used for initial load.
   */
  async function refreshNow(
    nodeId: string,
    getGraph: () => { nodes: any[]; edges: any[] },
  ): Promise<void> {
    const raw = getGraph()
    const graph = serializeGraph(raw)
    try {
      const result = await fetchNodeOutputSchema(nodeId, graph)
      resolvedOutputsByNodeId[nodeId] = result
    } catch {
      resolvedOutputsByNodeId[nodeId] = { resolved: false, columns: {} }
    }
  }

  /** Remove a node's resolved outputs (e.g. when the node is deleted). */
  function removeNode(nodeId: string): void {
    delete resolvedOutputsByNodeId[nodeId]
    if (_timers[nodeId]) {
      clearTimeout(_timers[nodeId])
      delete _timers[nodeId]
    }
  }

  /** Clear all resolved outputs. */
  function clear(): void {
    for (const key of Object.keys(resolvedOutputsByNodeId)) {
      delete resolvedOutputsByNodeId[key]
    }
    for (const key of Object.keys(_timers)) {
      clearTimeout(_timers[key])
      delete _timers[key]
    }
  }

  return {
    resolvedOutputsByNodeId,
    refreshResolvedOutputs,
    refreshNow,
    removeNode,
    clear,
  }
})
