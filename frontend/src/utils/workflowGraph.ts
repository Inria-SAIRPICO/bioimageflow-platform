import type {
  GraphState,
  MissingTool,
  ToolMetadata,
  ToolNodeState,
  WorkflowNodeState,
} from '@/api/types'
import { connectionSourceLabel } from '@/utils/displayNames'
import {
  encodeEndpointHandle,
} from '@/utils/endpointHandles'
import { reconcileOutputTemplates } from '@/utils/outputTemplates'

export interface VueFlowGraph {
  nodes: any[]
  edges: any[]
}

function sourceHandle(
  graph: GraphState,
  nodeId: string,
  output: string,
): string {
  const node = graph.nodes.find(candidate => candidate.id === nodeId)
  return encodeEndpointHandle(node?.type === 'workflow'
    ? { kind: 'workflow-output', id: output }
    : { kind: 'tool-output', name: output })
}

function targetHandle(
  graph: GraphState,
  nodeId: string,
  input: string,
): string {
  const node = graph.nodes.find(candidate => candidate.id === nodeId)
  return encodeEndpointHandle(node?.type === 'workflow'
    ? { kind: 'workflow-input', id: input }
    : { kind: 'tool-input', name: input })
}

function toolNodeData(
  node: ToolNodeState,
  tool: ToolMetadata | undefined,
  missingTool: MissingTool | null,
) {
  const pinnedInputs: Record<string, boolean> = {}
  if (tool) {
    for (const [name, field] of Object.entries(tool.inputs)) {
      if (field.connectable === 'never') continue
      const isPath = ['Path', 'ImageFile', 'MaskPath'].includes(field.type)
      pinnedInputs[name] = isPath && field.required
    }
  }
  return {
    nodeType: 'tool' as const,
    name: node.name,
    toolName: node.tool_name,
    tool: tool ?? null,
    missingTool,
    status: 'unexecuted',
    parameters: node.parameters,
    resources: node.resources ?? {},
    collapsed: node.collapsed ?? false,
    enabled: node.enabled ?? true,
    connectedInputs: {},
    pinnedInputs,
    output_templates: reconcileOutputTemplates(tool, node.output_templates ?? {}),
    toolModule: node.tool_module ?? null,
    toolClass: node.tool_class ?? null,
    toolPackage: node.tool_package ?? null,
    toolPackageVersion: node.tool_package_version ?? null,
    sourceModule: node.source_module ?? null,
  }
}

function workflowNodeData(node: WorkflowNodeState) {
  return {
    nodeType: 'workflow' as const,
    name: node.name,
    workflow: node.workflow,
    bindings: node.bindings,
    source: node.source ?? null,
    resources: node.resources ?? {},
    collapsed: node.collapsed ?? false,
    enabled: node.enabled ?? true,
    status: 'unexecuted',
    connectedInputs: {},
    pinnedInputs: Object.fromEntries(
      node.workflow.interface.inputs.map(input => [input.id, true]),
    ),
  }
}

export function graphStateToVueFlow(
  graph: GraphState,
  getToolByName: (name: string) => ToolMetadata | undefined,
  missingTools: MissingTool[] = [],
): VueFlowGraph {
  const missingByNode = new Map(missingTools.map(tool => [tool.node_id, tool]))
  const edges = graph.edges.map((edge) => {
    if (edge.type === 'dataframe') {
      return {
        id: edge.id,
        source: edge.source_node,
        target: edge.target_node,
        sourceHandle: encodeEndpointHandle({ kind: 'dataframe-output' }),
        targetHandle: edge.target_position == null
          ? encodeEndpointHandle({ kind: 'workflow-input', id: edge.target_input! })
          : encodeEndpointHandle({ kind: 'dataframe-position', index: edge.target_position }),
        type: 'dataframe',
      }
    }
    return {
      id: edge.id,
      source: edge.source_node,
      target: edge.target_node,
      sourceHandle: sourceHandle(graph, edge.source_node, edge.source_output),
      targetHandle: targetHandle(graph, edge.target_node, edge.target_input),
      type: 'column',
    }
  })
  const nodes = graph.nodes.map((node) => {
    const data = node.type === 'workflow'
      ? workflowNodeData(node)
      : toolNodeData(
          node,
          getToolByName(node.tool_name),
          missingByNode.get(node.id) ?? null,
        )
    return {
      id: node.id,
      type: node.type,
      position: { x: node.position[0], y: node.position[1] },
      data,
    }
  })

  const byId = new Map(nodes.map(node => [node.id, node]))
  for (const edge of edges) {
    const target = byId.get(edge.target)
    if (!target || !edge.targetHandle) continue
    const source = byId.get(edge.source)
    const connectedInputs = target.data.connectedInputs as Record<string, string>
    connectedInputs[edge.targetHandle] = connectionSourceLabel(
      source ?? { id: edge.source },
      edge.sourceHandle,
    )
  }
  return { nodes, edges }
}
