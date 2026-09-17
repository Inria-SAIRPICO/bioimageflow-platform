import type { GraphState } from '@/api/types'

export function emptyGraph(name = 'workflow', displayName = 'Workflow'): GraphState {
  return {
    schema_version: 2,
    name,
    display_name: displayName,
    nodes: [],
    edges: [],
    interface: { inputs: [], outputs: [] },
    config: {
      engine: 'wetlands',
      execution: 'parallel',
    },
  }
}

function sortJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortJson)
  if (typeof value !== 'object' || value === null) return value
  return Object.fromEntries(
    Object.entries(value)
      .filter(([, item]) => item !== undefined)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => [key, sortJson(item)]),
  )
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(sortJson(value))
}

export function canonicalGraphJson(graph: GraphState): string {
  return canonicalJson(graph)
}

export function graphDocumentsEqual(left: GraphState, right: GraphState): boolean {
  return canonicalGraphJson(left) === canonicalGraphJson(right)
}

export function jsonDocumentsEqual(left: unknown, right: unknown): boolean {
  return canonicalJson(left) === canonicalJson(right)
}
