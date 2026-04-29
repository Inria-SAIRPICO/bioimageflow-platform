import type { GraphState, MissingTool, ToolMetadata } from '@/api/types'

export interface VueFlowGraph {
  nodes: any[]
  edges: any[]
}

function sourceLabel(edge: any): string {
  const source = edge.source
  const sourceHandle = edge.sourceHandle ?? 'output'
  return `${source}.${sourceHandle}`
}

export function graphStateToVueFlow(
  graph: GraphState,
  getToolByName: (name: string) => ToolMetadata | undefined,
  missingTools: MissingTool[] = [],
): VueFlowGraph {
  const missingByNode = new Map(missingTools.map((tool) => [tool.node_id, tool]))
  const edges = graph.edges.map((edge) => {
    if (edge.type === 'positional') {
      return {
        id: edge.id,
        source: edge.source_node,
        target: edge.target_node,
        sourceHandle: '__dataframe_out',
        targetHandle: `__positional_${edge.positional_index}`,
        type: 'positional',
      }
    }
    return {
      id: edge.id,
      source: edge.source_node,
      target: edge.target_node,
      sourceHandle: edge.source_output,
      targetHandle: edge.target_input,
      type: 'column_ref',
    }
  })

  const connectedInputsByNode = new Map<string, Record<string, string>>()
  for (const edge of edges) {
    const targetHandle = edge.targetHandle ?? ''
    if (!targetHandle) continue
    const connected = connectedInputsByNode.get(edge.target) ?? {}
    connected[targetHandle] = sourceLabel(edge)
    connectedInputsByNode.set(edge.target, connected)
  }

  const nodes = graph.nodes.map((node) => {
    const tool = getToolByName(node.tool_name)
    const pinnedInputs: Record<string, boolean> = {}
    if (tool) {
      for (const [key, field] of Object.entries(tool.inputs)) {
        if (field.connectable !== 'never') {
          const isPathType = ['Path', 'ImagePath', 'MaskPath'].includes(field.type)
          pinnedInputs[key] = isPathType && field.required
        }
      }
    }

    return {
      id: node.id,
      type: 'tool',
      position: { x: node.position[0], y: node.position[1] },
      data: {
        name: node.name,
        toolName: node.tool_name,
        tool: tool ?? null,
        missingTool: missingByNode.get(node.id) ?? null,
        status: 'unexecuted',
        parameters: node.parameters ?? {},
        resources: node.resources ?? {},
        collapsed: node.collapsed ?? false,
        enabled: node.enabled ?? true,
        connectedInputs: connectedInputsByNode.get(node.id) ?? {},
        pinnedInputs,
        output_templates: node.output_templates ?? {},
      },
    }
  })

  return { nodes, edges }
}
