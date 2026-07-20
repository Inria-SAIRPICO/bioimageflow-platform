import type {
  GraphState,
  ToolNodeState,
  WorkflowNodeState,
  ValidationResult,
} from '@/api/types'

type NodeState = ToolNodeState | WorkflowNodeState

export function makeGraphNode(overrides: Partial<ToolNodeState> = {}): NodeState {
  return {
    type: 'tool',
    id: 'node',
    name: 'Node',
    tool_name: 'tool',
    position: [0, 0],
    parameters: {},
    resources: {},
    output_templates: {},
    enabled: true,
    collapsed: false,
    ...overrides,
  }
}

export function makeGraph(overrides: Partial<GraphState> = {}): GraphState {
  return {
    schema_version: 1,
    name: 'test_workflow',
    display_name: 'Test workflow',
    nodes: [],
    edges: [],
    interface: { inputs: [], outputs: [] },
    config: {
      storage_path: './bif_data',
      engine: 'wetlands',
      execution: 'parallel',
    },
    ...overrides,
  }
}

export function requireToolNode(graph: GraphState, index = 0): ToolNodeState {
  const node = graph.nodes[index]
  if (!node || node.type !== 'tool') {
    throw new Error(`Expected tool node at index ${index}`)
  }
  return node
}

export function makeValidationResult(
  overrides: Partial<ValidationResult> = {},
): ValidationResult {
  return {
    valid: true,
    node_statuses: {},
    errors: [],
    ...overrides,
  }
}
