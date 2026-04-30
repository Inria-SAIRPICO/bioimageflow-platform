import type { GraphState, PublishedInput, PublishedOutput } from '@/api/types'

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

export interface CreateSubWorkflowOptions {
  nodes: VueFlowNode[]
  edges: VueFlowEdge[]
  selectedNodeIds: Set<string>
  subWorkflowId: string
  subWorkflowName: string
}

export interface CreateSubWorkflowResult {
  nodes: VueFlowNode[]
  edges: VueFlowEdge[]
  subWorkflowNode: VueFlowNode
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function uniqueName(base: string, used: Set<string>): string {
  let name = base
  let suffix = 2
  while (used.has(name)) {
    name = `${base}_${suffix}`
    suffix += 1
  }
  used.add(name)
  return name
}

function schemaForInput(node: VueFlowNode | undefined, field: string): Record<string, any> | null {
  if (field.startsWith('__positional_')) return { type: 'DataFrame' }
  const schema = node?.data?.tool?.inputs?.[field]
  return schema == null ? null : deepClone(schema)
}

function schemaForOutput(node: VueFlowNode | undefined, output: string): Record<string, any> | null {
  if (output === '__dataframe_out') return { type: 'DataFrame' }
  const schema = node?.data?.tool?.outputs?.[output]
  return schema == null ? null : deepClone(schema)
}

function edgeToGraphState(edge: VueFlowEdge) {
  const sourceHandle = edge.sourceHandle ?? ''
  const targetHandle = edge.targetHandle ?? ''
  const headerEdge = sourceHandle === '__dataframe_out' || targetHandle.startsWith('__positional_')
  if (headerEdge) {
    const positionalIndex = parseInt(targetHandle.replace('__positional_', ''), 10)
    return {
      type: 'positional' as const,
      id: edge.id,
      source_node: edge.source,
      target_node: edge.target,
      positional_index: Number.isNaN(positionalIndex) ? 0 : positionalIndex,
    }
  }
  return {
    type: 'column_ref' as const,
    id: edge.id,
    source_node: edge.source,
    target_node: edge.target,
    source_output: sourceHandle,
    target_input: targetHandle,
  }
}

function nodeToGraphState(node: VueFlowNode) {
  const data = node.data ?? {}
  return {
    id: node.id,
    name: data.name ?? node.id,
    tool_name: data.toolName ?? '',
    position: [node.position?.x ?? 0, node.position?.y ?? 0] as [number, number],
    parameters: deepClone(data.parameters ?? {}),
    resources: deepClone(data.resources ?? {}),
    output_templates: deepClone(data.output_templates ?? {}),
    enabled: data.enabled ?? true,
    collapsed: data.collapsed ?? false,
    sub_workflow: data.sub_workflow == null ? undefined : deepClone(data.sub_workflow),
    published_inputs: deepClone(data.published_inputs ?? []),
    published_outputs: deepClone(data.published_outputs ?? []),
    sub_workflow_readonly_reason: data.sub_workflow_readonly_reason ?? null,
  }
}

export function createSubWorkflowFromSelection(
  options: CreateSubWorkflowOptions,
): CreateSubWorkflowResult {
  const selectedIds = options.selectedNodeIds
  if (selectedIds.size === 0) {
    throw new Error('Cannot create a sub-workflow without selected nodes')
  }

  const selectedNodes = options.nodes.filter((node) => selectedIds.has(node.id))
  if (selectedNodes.length === 0) {
    throw new Error('Selected node ids do not match any canvas nodes')
  }

  const selectedById = new Map(selectedNodes.map((node) => [node.id, node]))
  const internalEdges = options.edges.filter((edge) => (
    selectedIds.has(edge.source) && selectedIds.has(edge.target)
  ))
  const incomingEdges = options.edges.filter((edge) => (
    !selectedIds.has(edge.source) && selectedIds.has(edge.target)
  ))
  const outgoingEdges = options.edges.filter((edge) => (
    selectedIds.has(edge.source) && !selectedIds.has(edge.target)
  ))
  const untouchedEdges = options.edges.filter((edge) => (
    !selectedIds.has(edge.source) && !selectedIds.has(edge.target)
  ))

  const usedPinNames = new Set<string>()
  const publishedInputs: PublishedInput[] = incomingEdges.map((edge) => {
    const internalField = edge.targetHandle ?? ''
    const internalNode = selectedById.get(edge.target)
    const baseName = `${edge.target}.${internalField || 'input'}`
    const name = uniqueName(baseName, usedPinNames)
    return {
      name,
      internal_node_id: edge.target,
      internal_field: internalField,
      kind: 'input',
      schema: schemaForInput(internalNode, internalField),
      default: null,
    }
  })

  const outputNameByEdgeId = new Map<string, string>()
  const outputNameByRoute = new Map<string, string>()
  const publishedOutputs: PublishedOutput[] = []
  for (const edge of outgoingEdges) {
    const internalOutput = edge.sourceHandle ?? ''
    const routeKey = `${edge.source}:${internalOutput}:${edge.target}:${edge.targetHandle ?? ''}`
    let name = outputNameByRoute.get(routeKey)
    if (!name) {
      const internalNode = selectedById.get(edge.source)
      name = uniqueName(`${edge.source}.${internalOutput || 'output'}`, usedPinNames)
      outputNameByRoute.set(routeKey, name)
      publishedOutputs.push({
        name,
        internal_node_id: edge.source,
        internal_output: internalOutput,
        schema: schemaForOutput(internalNode, internalOutput),
      })
    }
    outputNameByEdgeId.set(edge.id, name)
  }

  const nestedGraph: GraphState = {
    nodes: selectedNodes.map(nodeToGraphState),
    edges: internalEdges.map(edgeToGraphState),
  }

  const centroid = selectedNodes.reduce(
    (acc, node) => ({
      x: acc.x + (node.position?.x ?? 0),
      y: acc.y + (node.position?.y ?? 0),
    }),
    { x: 0, y: 0 },
  )
  centroid.x /= selectedNodes.length
  centroid.y /= selectedNodes.length

  const connectedInputs: Record<string, string> = {}
  incomingEdges.forEach((edge, index) => {
    const published = publishedInputs[index]
    const source = options.nodes.find((node) => node.id === edge.source)
    const sourceName = source?.data?.name ?? edge.source
    connectedInputs[published.name] = `${sourceName}.${edge.sourceHandle ?? 'output'}`
  })

  const subWorkflowNode: VueFlowNode = {
    id: options.subWorkflowId,
    type: 'sub_workflow',
    selected: true,
    position: centroid,
    data: {
      name: options.subWorkflowName,
      toolName: '__sub_workflow__',
      tool: null,
      status: 'unexecuted',
      parameters: {},
      collapsed: false,
      enabled: true,
      connectedInputs,
      pinnedInputs: Object.fromEntries(publishedInputs.map((pin) => [pin.name, true])),
      output_templates: {},
      sub_workflow: nestedGraph,
      published_inputs: publishedInputs,
      published_outputs: publishedOutputs,
      sub_workflow_readonly_reason: null,
    },
  }

  const rewiredIncoming = incomingEdges.map((edge, index) => ({
    ...edge,
    target: options.subWorkflowId,
    targetHandle: publishedInputs[index].name,
  }))
  const rewiredOutgoing = outgoingEdges.map((edge) => ({
    ...edge,
    source: options.subWorkflowId,
    sourceHandle: outputNameByEdgeId.get(edge.id) ?? '',
  }))

  const outerNodes = [
    ...options.nodes.filter((node) => !selectedIds.has(node.id)).map((node) => ({
      ...node,
      selected: false,
    })),
    subWorkflowNode,
  ]
  const outerEdges = [
    ...untouchedEdges,
    ...rewiredIncoming,
    ...rewiredOutgoing,
  ]

  return {
    nodes: outerNodes,
    edges: outerEdges,
    subWorkflowNode,
  }
}
