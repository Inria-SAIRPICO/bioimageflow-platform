import type { GraphState, MissingTool, ToolMetadata } from '@/api/types'
import { reconcileOutputTemplates } from '@/utils/outputTemplates'
import { connectionSourceLabel } from '@/utils/displayNames'

export interface VueFlowGraph {
  nodes: any[]
  edges: any[]
}

function hasSubWorkflowFields(node: Record<string, any>): boolean {
  return node.tool_name === '__sub_workflow__'
    || (node.sub_workflow !== undefined && node.sub_workflow !== null)
    || (Array.isArray(node.published_inputs) && node.published_inputs.length > 0)
    || (Array.isArray(node.published_outputs) && node.published_outputs.length > 0)
    || typeof node.source_workflow_name === 'string'
    || (
      node.sub_workflow_readonly_reason !== undefined
      && node.sub_workflow_readonly_reason !== null
    )
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
  const connectedBodyInputsByNode = new Map<string, Set<string>>()
  const graphNodesById = new Map(graph.nodes.map((node) => [node.id, node]))
  for (const edge of edges) {
    const targetHandle = edge.targetHandle ?? ''
    if (!targetHandle) continue
    const connected = connectedInputsByNode.get(edge.target) ?? {}
    const source = graphNodesById.get(edge.source)
    connected[targetHandle] = connectionSourceLabel(source
      ? {
          id: source.id,
          data: {
            name: source.name,
            tool: getToolByName(source.tool_name) ?? null,
            published_outputs: source.published_outputs ?? [],
          },
        }
      : { id: edge.source }, edge.sourceHandle)
    connectedInputsByNode.set(edge.target, connected)
    if (edge.type === 'column_ref') {
      const bodyInputs = connectedBodyInputsByNode.get(edge.target) ?? new Set<string>()
      bodyInputs.add(targetHandle)
      connectedBodyInputsByNode.set(edge.target, bodyInputs)
    }
  }

  const nodes = graph.nodes.map((node) => {
    const tool = getToolByName(node.tool_name)
    const pinnedInputs: Record<string, boolean> = {}
    if (tool) {
      for (const [key, field] of Object.entries(tool.inputs)) {
        if (field.connectable !== 'never') {
          const isPathType = ['Path', 'ImageFile', 'MaskPath'].includes(field.type)
          pinnedInputs[key] = isPathType && field.required
        }
      }
    }
    const isSubWorkflow = hasSubWorkflowFields(node as any)
    if (!isSubWorkflow && tool) {
      for (const targetHandle of connectedBodyInputsByNode.get(node.id) ?? []) {
        const field = tool.inputs[targetHandle]
        if (field && field.connectable !== 'never') {
          pinnedInputs[targetHandle] = true
        }
      }
    }

    const data: Record<string, unknown> = {
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
      output_templates: reconcileOutputTemplates(tool, node.output_templates ?? {}),
    }
    if (isSubWorkflow) {
      data.sub_workflow = (node as any).sub_workflow ?? null
      data.published_inputs = (node as any).published_inputs ?? []
      data.published_outputs = (node as any).published_outputs ?? []
      data.sub_workflow_readonly_reason =
        (node as any).sub_workflow_readonly_reason ?? null
      data.source_workflow_name = (node as any).source_workflow_name ?? null
    }

    return {
      id: node.id,
      type: isSubWorkflow ? 'sub_workflow' : 'tool',
      position: { x: node.position[0], y: node.position[1] },
      data,
    }
  })

  return { nodes, edges }
}
