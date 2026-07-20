import type {
  GraphState,
  WorkflowInput,
  WorkflowOutput,
} from '@/api/types'
import {
  decodeEndpointHandle,
  encodeEndpointHandle,
} from '@/utils/endpointHandles'
import { connectionSourceLabel } from '@/utils/displayNames'

type VueFlowNode = {
  id: string
  type?: string
  selected?: boolean
  position?: { x?: number; y?: number }
  data?: Record<string, any>
}

type VueFlowEdge = {
  id: string
  source: string
  target: string
  sourceHandle?: string | null
  targetHandle?: string | null
  type?: string
  selected?: boolean
  data?: Record<string, any>
}

export interface GroupIntoWorkflowOptions {
  nodes: VueFlowNode[]
  edges: VueFlowEdge[]
  selectedNodeIds: Set<string>
  workflowNodeId: string
  workflowNodeName: string
}

export interface GroupIntoWorkflowResult {
  nodes: VueFlowNode[]
  edges: VueFlowEdge[]
  workflowNode: VueFlowNode
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function uniqueName(base: string, used: Set<string>): string {
  let candidate = base
  let suffix = 2
  while (used.has(candidate)) candidate = `${base}_${suffix++}`
  used.add(candidate)
  return candidate
}

function stablePortId(direction: 'input' | 'output', edgeId: string, index: number): string {
  return `${direction}-${edgeId || index}`
}

function schemaForInput(node: VueFlowNode | undefined, name: string) {
  const schema = node?.data?.tool?.inputs?.[name]
  return schema == null ? null : clone(schema)
}

function schemaForOutput(node: VueFlowNode | undefined, name: string) {
  const schema = node?.data?.tool?.outputs?.[name]
  return schema == null ? null : clone(schema)
}

function serializeNode(node: VueFlowNode): GraphState['nodes'][number] {
  const data = node.data ?? {}
  const common = {
    id: node.id,
    name: data.name ?? node.id,
    position: [node.position?.x ?? 0, node.position?.y ?? 0] as [number, number],
    resources: clone(data.resources ?? {}),
    enabled: data.enabled ?? true,
    collapsed: data.collapsed ?? false,
  }
  if (node.type === 'workflow') {
    return {
      type: 'workflow',
      ...common,
      workflow: clone(data.workflow),
      bindings: clone(data.bindings ?? {}),
      source: data.source == null ? null : clone(data.source),
    }
  }
  return {
    type: 'tool',
    ...common,
    tool_name: data.toolName,
    parameters: clone(data.parameters ?? {}),
    output_templates: clone(data.output_templates ?? {}),
    tool_module: data.toolModule ?? null,
    tool_class: data.toolClass ?? null,
    tool_package: data.toolPackage ?? null,
    tool_package_version: data.toolPackageVersion ?? null,
    source_module: data.sourceModule ?? null,
  }
}

function serializeEdge(edge: VueFlowEdge): GraphState['edges'][number] {
  const source = decodeEndpointHandle(edge.sourceHandle ?? '')
  const target = decodeEndpointHandle(edge.targetHandle ?? '')
  if (source.kind === 'dataframe-output') {
    if (target.kind === 'dataframe-position') {
      return {
        type: 'dataframe',
        id: edge.id,
        source_node: edge.source,
        target_node: edge.target,
        target_position: target.index,
        target_input: null,
      }
    }
    if (target.kind === 'workflow-input' || target.kind === 'dataframe-input') {
      return {
        type: 'dataframe',
        id: edge.id,
        source_node: edge.source,
        target_node: edge.target,
        target_position: null,
        target_input: target.kind === 'workflow-input' ? target.id : target.name,
      }
    }
    throw new Error('DataFrame outputs require a DataFrame target')
  }
  if (source.kind !== 'tool-output' && source.kind !== 'workflow-output') {
    throw new Error('Column edges require an output endpoint')
  }
  if (target.kind !== 'tool-input' && target.kind !== 'workflow-input') {
    throw new Error('Column edges require a field input endpoint')
  }
  return {
    type: 'column',
    id: edge.id,
    source_node: edge.source,
    target_node: edge.target,
    source_output: source.kind === 'workflow-output' ? source.id : source.name,
    target_input: target.kind === 'workflow-input' ? target.id : target.name,
  }
}

export function groupIntoWorkflow(
  options: GroupIntoWorkflowOptions,
): GroupIntoWorkflowResult {
  if (options.selectedNodeIds.size === 0) {
    throw new Error('Cannot group an empty selection')
  }
  const selectedNodes = options.nodes.filter(node => options.selectedNodeIds.has(node.id))
  if (selectedNodes.length === 0) throw new Error('The selected nodes are not on this canvas')

  const selectedById = new Map(selectedNodes.map(node => [node.id, node]))
  const internalEdges = options.edges.filter(edge => (
    options.selectedNodeIds.has(edge.source) && options.selectedNodeIds.has(edge.target)
  ))
  const incomingEdges = options.edges.filter(edge => (
    !options.selectedNodeIds.has(edge.source) && options.selectedNodeIds.has(edge.target)
  ))
  const outgoingEdges = options.edges.filter(edge => (
    options.selectedNodeIds.has(edge.source) && !options.selectedNodeIds.has(edge.target)
  ))
  const untouchedEdges = options.edges.filter(edge => (
    !options.selectedNodeIds.has(edge.source) && !options.selectedNodeIds.has(edge.target)
  ))

  const names = new Set<string>()
  const inputs: WorkflowInput[] = incomingEdges.map((edge, index) => {
    const target = decodeEndpointHandle(edge.targetHandle ?? '')
    const id = stablePortId('input', edge.id, index)
    const base = `${edge.target}.${target.kind === 'dataframe-position' ? `table_${target.index}` : 'name' in target ? target.name : id}`
    if (target.kind === 'dataframe-position') {
      return {
        id,
        name: uniqueName(base, names),
        kind: 'dataframe',
        schema: { type: 'DataFrame' },
        default: null,
        targets: [{ node: edge.target, port: { kind: 'positional', index: target.index } }],
      }
    }
    if (target.kind !== 'tool-input' && target.kind !== 'workflow-input') {
      throw new Error('Incoming column edge has an incompatible target')
    }
    return {
      id,
      name: uniqueName(base, names),
      kind: 'field',
      schema: target.kind === 'tool-input'
        ? schemaForInput(selectedById.get(edge.target), target.name)
        : null,
      default: null,
      targets: [{
        node: edge.target,
        port: target.kind === 'workflow-input'
          ? { kind: 'workflow', id: target.id }
          : { kind: 'field', name: target.name },
      }],
    }
  })

  const outputByRoute = new Map<string, WorkflowOutput>()
  outgoingEdges.forEach((edge, index) => {
    const source = decodeEndpointHandle(edge.sourceHandle ?? '')
    if (source.kind === 'dataframe-output') return
    if (source.kind !== 'tool-output' && source.kind !== 'workflow-output') {
      throw new Error('Outgoing column edge has an incompatible source')
    }
    const column = source.kind === 'workflow-output' ? source.id : source.name
    const route = `${edge.source}:${column}`
    if (outputByRoute.has(route)) return
    outputByRoute.set(route, {
      id: stablePortId('output', edge.id, index),
      name: uniqueName(`${edge.source}.${column}`, names),
      schema: source.kind === 'tool-output'
        ? schemaForOutput(selectedById.get(edge.source), source.name)
        : null,
      source: { node: edge.source, column },
    })
  })
  const outputs = [...outputByRoute.values()]

  const workflow: GraphState = {
    schema_version: 1,
    name: options.workflowNodeName,
    display_name: options.workflowNodeName,
    nodes: selectedNodes.map(serializeNode),
    edges: internalEdges.map(serializeEdge),
    interface: { inputs, outputs },
    config: { storage_path: './bif_data', engine: 'wetlands', execution: 'parallel' },
  }
  const centroid = selectedNodes.reduce(
    (point, node) => ({
      x: point.x + (node.position?.x ?? 0),
      y: point.y + (node.position?.y ?? 0),
    }),
    { x: 0, y: 0 },
  )
  centroid.x /= selectedNodes.length
  centroid.y /= selectedNodes.length

  const connectedInputs: Record<string, string> = {}
  incomingEdges.forEach((edge, index) => {
    connectedInputs[encodeEndpointHandle({ kind: 'workflow-input', id: inputs[index].id })]
      = connectionSourceLabel(
        options.nodes.find(node => node.id === edge.source) ?? { id: edge.source },
        edge.sourceHandle,
      )
  })
  const workflowNode: VueFlowNode = {
    id: options.workflowNodeId,
    type: 'workflow',
    selected: true,
    position: centroid,
    data: {
      nodeType: 'workflow',
      name: options.workflowNodeName,
      workflow,
      bindings: {},
      source: null,
      resources: {},
      enabled: true,
      collapsed: false,
      connectedInputs,
      pinnedInputs: Object.fromEntries(inputs.map(input => [input.id, true])),
    },
  }

  const rewiredIncoming = incomingEdges.map((edge, index) => ({
    ...edge,
    target: options.workflowNodeId,
    targetHandle: encodeEndpointHandle({ kind: 'workflow-input', id: inputs[index].id }),
  }))
  const rewiredOutgoing = outgoingEdges.map((edge) => {
    const source = decodeEndpointHandle(edge.sourceHandle ?? '')
    if (source.kind === 'dataframe-output') {
      return { ...edge, source: options.workflowNodeId }
    }
    if (source.kind !== 'tool-output' && source.kind !== 'workflow-output') {
      throw new Error('Outgoing column edge has an incompatible source')
    }
    const column = source.kind === 'workflow-output' ? source.id : source.name
    const output = outputByRoute.get(`${edge.source}:${column}`)
    if (!output) throw new Error('Workflow output was not created')
    return {
      ...edge,
      source: options.workflowNodeId,
      sourceHandle: encodeEndpointHandle({ kind: 'workflow-output', id: output.id }),
    }
  })

  return {
    nodes: [
      ...options.nodes
        .filter(node => !options.selectedNodeIds.has(node.id))
        .map(node => ({ ...node, selected: false })),
      workflowNode,
    ],
    edges: [...untouchedEdges, ...rewiredIncoming, ...rewiredOutgoing],
    workflowNode,
  }
}
