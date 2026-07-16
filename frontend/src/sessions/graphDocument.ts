import type { GraphState, PublishedInput, PublishedOutput } from '@/api/types'

function normalizePublishedInput(input: PublishedInput): Record<string, unknown> {
  const normalized = { ...input } as Record<string, unknown>
  if (normalized.schema == null) delete normalized.schema
  if (normalized.default == null) delete normalized.default
  return normalized
}

function normalizePublishedOutput(output: PublishedOutput): Record<string, unknown> {
  const normalized = { ...output } as Record<string, unknown>
  if (normalized.schema == null) delete normalized.schema
  return normalized
}

function normalizeGraph(graph: GraphState): Record<string, unknown> {
  return {
    nodes: graph.nodes.map((node) => {
      const normalized = {
        ...node,
        resources: node.resources ?? {},
        output_templates: node.output_templates ?? {},
        enabled: node.enabled ?? true,
        collapsed: node.collapsed ?? false,
      } as Record<string, unknown>
      if (node.sub_workflow == null) {
        delete normalized.sub_workflow
      } else {
        normalized.sub_workflow = normalizeGraph(node.sub_workflow)
      }
      const inputs = node.published_inputs ?? []
      if (inputs.length === 0) delete normalized.published_inputs
      else normalized.published_inputs = inputs.map(normalizePublishedInput)
      const outputs = node.published_outputs ?? []
      if (outputs.length === 0) delete normalized.published_outputs
      else normalized.published_outputs = outputs.map(normalizePublishedOutput)
      if (node.sub_workflow_readonly_reason == null) {
        delete normalized.sub_workflow_readonly_reason
      }
      if (node.source_workflow_name == null) {
        delete normalized.source_workflow_name
      }
      return normalized
    }),
    edges: graph.edges.map(edge => ({
      ...edge,
      type: edge.type ?? ('positional_index' in edge ? 'positional' : 'column_ref'),
    })),
    published_inputs: (graph.published_inputs ?? []).map(normalizePublishedInput),
    published_outputs: (graph.published_outputs ?? []).map(normalizePublishedOutput),
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

export function canonicalGraphJson(graph: GraphState): string {
  return JSON.stringify(sortJson(normalizeGraph(graph)))
}

export function graphDocumentsEqual(left: GraphState, right: GraphState): boolean {
  return canonicalGraphJson(left) === canonicalGraphJson(right)
}
