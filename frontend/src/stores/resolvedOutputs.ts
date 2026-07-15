import { computed, reactive, shallowReactive } from 'vue'
import { defineStore } from 'pinia'
import { fetchNodeOutputSchema } from '@/api/client'
import { serializeGraph } from '@/composables/useGraphSync'
import type { NodeOutputSchemaResponse, ToolMetadata } from '@/api/types'
import {
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'

type RawGraph = { nodes: any[]; edges: any[] }
type SerializedGraph = ReturnType<typeof serializeGraph>
type GraphGetter = () => RawGraph
type ToolGetter = (nodeId: string) => ToolMetadata | undefined

interface ResolvedOutputContext {
  readonly outputs: Record<string, NodeOutputSchemaResponse>
  readonly timers: Map<string, ReturnType<typeof setTimeout>>
  readonly requestIds: Map<string, number>
  released: boolean
}

interface ResolvedOutputRequest {
  nodeId: string
  requestId: number
}

const EMPTY_OUTPUTS = Object.freeze({}) as Record<string, NodeOutputSchemaResponse>

function createContext(): ResolvedOutputContext {
  return {
    outputs: reactive<Record<string, NodeOutputSchemaResponse>>({}),
    timers: new Map(),
    requestIds: new Map(),
    released: false,
  }
}

export const useResolvedOutputsStore = defineStore('resolvedOutputs', () => {
  const legacyContext = createContext()
  const canvasContexts = shallowReactive(new Map<CanvasId, ResolvedOutputContext>())
  const releasedCanvasIds = new Set<CanvasId>()

  function contextForCanvas(canvasId: CanvasId): ResolvedOutputContext | null {
    if (releasedCanvasIds.has(canvasId)) return null
    const existing = canvasContexts.get(canvasId)
    if (existing) return existing
    const created = createContext()
    canvasContexts.set(canvasId, created)
    return created
  }

  function existingCanvasContext(canvasId: CanvasId): ResolvedOutputContext | null {
    return canvasContexts.get(canvasId) ?? null
  }

  function activeContext(create: boolean): ResolvedOutputContext | null {
    const canvasId = canvasSessionRegistry.activeCanvasId.value
    if (canvasId !== null) {
      return create
        ? contextForCanvas(canvasId)
        : existingCanvasContext(canvasId)
    }
    return canvasSessionRegistry.sessionCount.value === 0
      ? legacyContext
      : null
  }

  const resolvedOutputsByNodeId = computed(() => (
    activeContext(false)?.outputs ?? EMPTY_OUTPUTS
  ))

  function resolvedOutputsForCanvas(
    canvasId: CanvasId,
  ): Record<string, NodeOutputSchemaResponse> {
    releasedCanvasIds.delete(canvasId)
    const context = contextForCanvas(canvasId)
    if (context === null) throw new Error(`Could not register canvas '${canvasId}'`)
    return context.outputs
  }

  function getCanvasResolvedOutput(
    canvasId: CanvasId,
    nodeId: string,
  ): NodeOutputSchemaResponse | undefined {
    return existingCanvasContext(canvasId)?.outputs[nodeId]
  }

  function nextRequestId(context: ResolvedOutputContext, nodeId: string): number {
    const requestId = (context.requestIds.get(nodeId) ?? 0) + 1
    context.requestIds.set(nodeId, requestId)
    return requestId
  }

  function isCurrentRequest(
    context: ResolvedOutputContext,
    nodeId: string,
    requestId: number,
  ): boolean {
    return !context.released && context.requestIds.get(nodeId) === requestId
  }

  function clearTimer(context: ResolvedOutputContext, nodeId: string): void {
    const timer = context.timers.get(nodeId)
    if (timer !== undefined) {
      clearTimeout(timer)
      context.timers.delete(nodeId)
    }
  }

  async function fetchAndPublish(
    context: ResolvedOutputContext,
    nodeId: string,
    graph: SerializedGraph,
    requestId: number,
    origin?: ResolvedOutputRequest,
  ): Promise<boolean> {
    let result: NodeOutputSchemaResponse
    try {
      result = await fetchNodeOutputSchema(nodeId, graph)
    } catch {
      result = { resolved: false, columns: {} }
    }
    if (
      !isCurrentRequest(context, nodeId, requestId)
      || (
        origin !== undefined
        && !isCurrentRequest(context, origin.nodeId, origin.requestId)
      )
    ) return false
    context.outputs[nodeId] = result
    return true
  }

  function refreshInContext(
    context: ResolvedOutputContext,
    nodeId: string,
    getGraph: GraphGetter,
    getToolForNode: ToolGetter,
  ): void {
    if (context.released) return
    clearTimer(context, nodeId)
    const requestId = nextRequestId(context, nodeId)
    const timer = setTimeout(async () => {
      if (context.timers.get(nodeId) === timer) {
        context.timers.delete(nodeId)
      }
      if (!isCurrentRequest(context, nodeId, requestId)) return
      const raw = getGraph()
      const graph = serializeGraph(raw)
      const published = await fetchAndPublish(context, nodeId, graph, requestId)
      if (!published) return
      await propagateDownstream(
        context,
        nodeId,
        requestId,
        raw,
        graph,
        getToolForNode,
      )
    }, 200)
    context.timers.set(nodeId, timer)
  }

  function refreshResolvedOutputs(
    nodeId: string,
    getGraph: GraphGetter,
    getToolForNode: ToolGetter,
  ): void {
    const context = activeContext(true)
    if (context) refreshInContext(context, nodeId, getGraph, getToolForNode)
  }

  function refreshCanvasResolvedOutputs(
    canvasId: CanvasId,
    nodeId: string,
    getGraph: GraphGetter,
    getToolForNode: ToolGetter,
  ): void {
    const context = contextForCanvas(canvasId)
    if (context) refreshInContext(context, nodeId, getGraph, getToolForNode)
  }

  async function propagateDownstream(
    context: ResolvedOutputContext,
    startNodeId: string,
    startRequestId: number,
    raw: RawGraph,
    graph: SerializedGraph,
    getToolForNode: ToolGetter,
  ): Promise<void> {
    const visited = new Set<string>()
    const queue = [startNodeId]

    while (queue.length > 0) {
      if (!isCurrentRequest(context, startNodeId, startRequestId)) return
      const current = queue.shift()!
      if (visited.has(current)) continue
      visited.add(current)

      for (const edge of raw.edges) {
        if (edge.source !== current) continue
        const targetHandle = edge.targetHandle ?? ''
        if (!targetHandle.startsWith('__positional_')) continue
        const targetId = edge.target
        if (visited.has(targetId)) continue

        const targetTool = getToolForNode(targetId)
        if (targetTool?.dynamic_outputs === true) {
          clearTimer(context, targetId)
          const requestId = nextRequestId(context, targetId)
          const published = await fetchAndPublish(
            context,
            targetId,
            graph,
            requestId,
            { nodeId: startNodeId, requestId: startRequestId },
          )
          if (!isCurrentRequest(context, startNodeId, startRequestId)) return
          if (!published) continue
          queue.push(targetId)
        }
      }
    }
  }

  async function refreshNowInContext(
    context: ResolvedOutputContext,
    nodeId: string,
    getGraph: GraphGetter,
  ): Promise<void> {
    if (context.released) return
    clearTimer(context, nodeId)
    const requestId = nextRequestId(context, nodeId)
    const graph = serializeGraph(getGraph())
    await fetchAndPublish(context, nodeId, graph, requestId)
  }

  function refreshNow(nodeId: string, getGraph: GraphGetter): Promise<void> {
    const context = activeContext(true)
    return context
      ? refreshNowInContext(context, nodeId, getGraph)
      : Promise.resolve()
  }

  function refreshCanvasNow(
    canvasId: CanvasId,
    nodeId: string,
    getGraph: GraphGetter,
  ): Promise<void> {
    const context = contextForCanvas(canvasId)
    return context
      ? refreshNowInContext(context, nodeId, getGraph)
      : Promise.resolve()
  }

  function removeNodeFromContext(
    context: ResolvedOutputContext,
    nodeId: string,
  ): void {
    clearTimer(context, nodeId)
    nextRequestId(context, nodeId)
    delete context.outputs[nodeId]
  }

  function removeNode(nodeId: string): void {
    const context = activeContext(false)
    if (context) removeNodeFromContext(context, nodeId)
  }

  function removeCanvasNode(canvasId: CanvasId, nodeId: string): void {
    const context = existingCanvasContext(canvasId)
    if (context) removeNodeFromContext(context, nodeId)
  }

  function clearContext(context: ResolvedOutputContext): void {
    const nodeIds = new Set([
      ...Object.keys(context.outputs),
      ...context.timers.keys(),
      ...context.requestIds.keys(),
    ])
    for (const nodeId of nodeIds) removeNodeFromContext(context, nodeId)
  }

  function clear(): void {
    const context = activeContext(false)
    if (context) clearContext(context)
  }

  function clearCanvas(canvasId: CanvasId): void {
    const context = existingCanvasContext(canvasId)
    if (context) clearContext(context)
  }

  function releaseCanvas(canvasId: CanvasId): void {
    releasedCanvasIds.add(canvasId)
    const context = existingCanvasContext(canvasId)
    if (!context) return
    context.released = true
    for (const timer of context.timers.values()) clearTimeout(timer)
    context.timers.clear()
    for (const nodeId of Object.keys(context.outputs)) delete context.outputs[nodeId]
    context.requestIds.clear()
    canvasContexts.delete(canvasId)
  }

  return {
    resolvedOutputsByNodeId,
    resolvedOutputsForCanvas,
    getCanvasResolvedOutput,
    refreshResolvedOutputs,
    refreshCanvasResolvedOutputs,
    refreshNow,
    refreshCanvasNow,
    removeNode,
    removeCanvasNode,
    clear,
    clearCanvas,
    releaseCanvas,
  }
})
