import type {
  GraphState,
  NodeState,
  ValidationResult,
} from '@/api/types'

export function makeGraphNode(overrides: Partial<NodeState> = {}): NodeState {
  return {
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
    nodes: [],
    edges: [],
    ...overrides,
  }
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
