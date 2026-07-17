import type { GraphState } from '@/api/types'

export interface ResolvedDataTableNode {
  nodeId: string
  role: 'anchor' | 'context'
}

function incomingByTarget(graph: GraphState): Map<string, string[]> {
  const incoming = new Map<string, string[]>()
  for (const edge of graph.edges) {
    const sources = incoming.get(edge.target_node) ?? []
    if (!sources.includes(edge.source_node)) sources.push(edge.source_node)
    incoming.set(edge.target_node, sources)
  }
  return incoming
}

function topologicalRanks(graph: GraphState): Map<string, number> {
  const order = new Map(graph.nodes.map((node, index) => [node.id, index]))
  const indegree = new Map(graph.nodes.map((node) => [node.id, 0]))
  const outgoing = new Map<string, string[]>()
  for (const edge of graph.edges) {
    if (!indegree.has(edge.source_node) || !indegree.has(edge.target_node)) continue
    indegree.set(edge.target_node, (indegree.get(edge.target_node) ?? 0) + 1)
    const targets = outgoing.get(edge.source_node) ?? []
    targets.push(edge.target_node)
    outgoing.set(edge.source_node, targets)
  }
  const ready = graph.nodes
    .filter((node) => indegree.get(node.id) === 0)
    .map((node) => node.id)
  const ranks = new Map<string, number>()
  let rank = 0
  while (ready.length > 0) {
    ready.sort((left, right) => (order.get(left) ?? 0) - (order.get(right) ?? 0))
    const nodeId = ready.shift()!
    ranks.set(nodeId, rank++)
    for (const target of outgoing.get(nodeId) ?? []) {
      indegree.set(target, (indegree.get(target) ?? 1) - 1)
      if (indegree.get(target) === 0) ready.push(target)
    }
  }
  for (const node of graph.nodes) {
    if (!ranks.has(node.id)) ranks.set(node.id, rank++)
  }
  return ranks
}

export function maximumUpstreamDepth(graph: GraphState, selectedNodeIds: string[]): number {
  const incoming = incomingByTarget(graph)
  const distances = new Map(selectedNodeIds.map((nodeId) => [nodeId, 0]))
  const queue = [...selectedNodeIds]
  let maximum = 0
  while (queue.length > 0) {
    const nodeId = queue.shift()!
    const distance = distances.get(nodeId) ?? 0
    for (const source of incoming.get(nodeId) ?? []) {
      const nextDistance = distance + 1
      const previous = distances.get(source)
      if (previous !== undefined && previous <= nextDistance) continue
      distances.set(source, nextDistance)
      maximum = Math.max(maximum, nextDistance)
      queue.push(source)
    }
  }
  return maximum
}

export function resolveDataTableNodes(
  graph: GraphState,
  selectedNodeIds: string[],
  upstreamDepth: number,
): ResolvedDataTableNode[] {
  const existing = new Set(graph.nodes.map((node) => node.id))
  const anchors = new Set(selectedNodeIds.filter((nodeId) => existing.has(nodeId)))
  const incoming = incomingByTarget(graph)
  const included = new Set(anchors)
  let frontier = [...anchors]
  for (let level = 0; level < upstreamDepth; level += 1) {
    const next: string[] = []
    for (const nodeId of frontier) {
      for (const source of incoming.get(nodeId) ?? []) {
        if (included.has(source)) continue
        included.add(source)
        next.push(source)
      }
    }
    frontier = next
    if (frontier.length === 0) break
  }
  const ranks = topologicalRanks(graph)
  return [...included]
    .sort((left, right) => (ranks.get(left) ?? 0) - (ranks.get(right) ?? 0))
    .map((nodeId) => ({ nodeId, role: anchors.has(nodeId) ? 'anchor' : 'context' }))
}

export function selectedAnchorsAreRelated(
  graph: GraphState,
  selectedNodeIds: string[],
): boolean {
  if (selectedNodeIds.length < 2) return true
  const selected = new Set(selectedNodeIds)
  const adjacent = new Map<string, string[]>()
  for (const edge of graph.edges) {
    adjacent.set(edge.source_node, [...(adjacent.get(edge.source_node) ?? []), edge.target_node])
    adjacent.set(edge.target_node, [...(adjacent.get(edge.target_node) ?? []), edge.source_node])
  }
  const seen = new Set<string>()
  const queue = [selectedNodeIds[0]]
  while (queue.length > 0) {
    const nodeId = queue.shift()!
    if (seen.has(nodeId)) continue
    seen.add(nodeId)
    queue.push(...(adjacent.get(nodeId) ?? []))
  }
  return [...selected].every((nodeId) => seen.has(nodeId))
}
