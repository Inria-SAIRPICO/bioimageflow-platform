import { describe, expect, it } from 'vitest'
import type { GraphState, NodeState } from '@/api/types'
import {
  maximumUpstreamDepth,
  resolveDataTableNodes,
  selectedAnchorsAreRelated,
} from '@/utils/dataTableSources'

function node(id: string): NodeState {
  return {
    id,
    name: id,
    tool_name: id,
    position: [0, 0],
    parameters: {},
    resources: {},
    output_templates: {},
    enabled: true,
    collapsed: false,
  }
}

function edge(id: string, source: string, target: string) {
  return {
    id,
    type: 'positional' as const,
    source_node: source,
    target_node: target,
    positional_index: 0,
  }
}

const graph: GraphState = {
  nodes: ['a', 'branch', 'b', 'c', 'independent'].map(node),
  edges: [
    edge('a-b', 'a', 'b'),
    edge('branch-b', 'branch', 'b'),
    edge('b-c', 'b', 'c'),
  ],
}

describe('Data Table source traversal', () => {
  it('collects incoming branches to the requested depth and orders them topologically', () => {
    expect(resolveDataTableNodes(graph, ['c'], 2)).toEqual([
      { nodeId: 'a', role: 'context' },
      { nodeId: 'branch', role: 'context' },
      { nodeId: 'b', role: 'context' },
      { nodeId: 'c', role: 'anchor' },
    ])
    expect(maximumUpstreamDepth(graph, ['c'])).toBe(2)
  })

  it('deduplicates overlapping traversal and lets explicit selection override context', () => {
    expect(resolveDataTableNodes(graph, ['b', 'c'], 2)).toEqual([
      { nodeId: 'a', role: 'context' },
      { nodeId: 'branch', role: 'context' },
      { nodeId: 'b', role: 'anchor' },
      { nodeId: 'c', role: 'anchor' },
    ])
  })

  it('distinguishes connected selections from independent selections', () => {
    expect(selectedAnchorsAreRelated(graph, ['a', 'c'])).toBe(true)
    expect(selectedAnchorsAreRelated(graph, ['c', 'independent'])).toBe(false)
  })
})
