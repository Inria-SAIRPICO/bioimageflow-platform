import type { GraphState, GraphValidationError, NodeStatus } from '@/api/types'

type EdgeLike = {
  id?: string
  source_node?: string
  target_node?: string
  source?: string
  target?: string
}

function edgeSource(edge: EdgeLike): string | null {
  return edge.source_node ?? edge.source ?? null
}

function edgeTarget(edge: EdgeLike): string | null {
  return edge.target_node ?? edge.target ?? null
}

export function collectExecutionNodeIds(
  graph: GraphState,
  selectedNodeIds?: string[],
): Set<string> | null {
  if (!selectedNodeIds || selectedNodeIds.length === 0) return null

  const executable = new Set(selectedNodeIds)
  const incoming = new Map<string, string[]>()
  for (const edge of graph.edges as EdgeLike[]) {
    const source = edgeSource(edge)
    const target = edgeTarget(edge)
    if (!source || !target) continue
    const sources = incoming.get(target) ?? []
    sources.push(source)
    incoming.set(target, sources)
  }

  const stack = [...executable]
  while (stack.length > 0) {
    const nodeId = stack.pop()!
    for (const upstream of incoming.get(nodeId) ?? []) {
      if (executable.has(upstream)) continue
      executable.add(upstream)
      stack.push(upstream)
    }
  }
  return executable
}

export function collectExecutionEdgeIds(
  graph: GraphState,
  executionNodeIds: Set<string> | null,
): Set<string> | null {
  if (executionNodeIds === null) return null
  const edgeIds = new Set<string>()
  for (const edge of graph.edges as EdgeLike[]) {
    const source = edgeSource(edge)
    const target = edgeTarget(edge)
    if (
      edge.id &&
      source &&
      target &&
      executionNodeIds.has(source) &&
      executionNodeIds.has(target)
    ) {
      edgeIds.add(edge.id)
    }
  }
  return edgeIds
}

export function validationErrorsForExecution(
  errors: GraphValidationError[],
  graph: GraphState,
  selectedNodeIds?: string[],
): GraphValidationError[] {
  const executionNodeIds = collectExecutionNodeIds(graph, selectedNodeIds)
  if (executionNodeIds === null) return errors
  const executionEdgeIds = collectExecutionEdgeIds(graph, executionNodeIds)
  return errors.filter((error) => {
    if (error.node) return executionNodeIds.has(error.node)
    if (error.edge_id) return executionEdgeIds?.has(error.edge_id) ?? false
    return true
  })
}

export function outOfDateNodeIdsForExecution(
  nodeStatuses: Record<string, NodeStatus> | undefined,
  graph: GraphState,
  selectedNodeIds?: string[],
): string[] {
  const executionNodeIds = collectExecutionNodeIds(graph, selectedNodeIds)
  return Object.values(nodeStatuses ?? {})
    .filter((status) => status.status === 'out_of_date')
    .filter((status) =>
      executionNodeIds === null ? true : executionNodeIds.has(status.node_id),
    )
    .map((status) => status.node_id)
}
