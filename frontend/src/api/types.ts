/**
 * Placeholder type interfaces for the BioImageFlow API.
 *
 * These will be overwritten by generated types when running
 * scripts/generate-types.sh against a live backend.
 */

export interface InputFieldSchema {
  type: string
  connectable: boolean
  default?: unknown
  description?: string
  min?: number
  max?: number
  step?: number
  group?: string
}

export interface OutputFieldSchema {
  type: string
}

export interface ToolMetadata {
  name: string
  display_name: string
  package: string
  tool_type: string
  documentation: string
  tags: string[]
  categories: string[]
  inputs: Record<string, InputFieldSchema>
  outputs: Record<string, OutputFieldSchema>
  environment: string
}

export interface PackageInfo {
  name: string
  installed_versions: string[]
  available_versions: string[]
  tools: Record<string, ToolMetadata>
  environment_status: string
}

export interface NodeState {
  id: string
  type: string
  tool_name: string
  position: { x: number; y: number }
  parameters: Record<string, unknown>
}

export interface Edge {
  id: string
  source: string
  sourceHandle: string
  target: string
  targetHandle: string
}

export interface GraphState {
  nodes: NodeState[]
  edges: Edge[]
}

export type NodeStatus = 'idle' | 'running' | 'success' | 'error' | 'outdated'

export interface GraphValidationError {
  nodeId: string
  field?: string
  message: string
  severity: string
}

export interface ValidationResult {
  valid: boolean
  errors: GraphValidationError[]
}

export interface ErrorResponse {
  error: string
  detail: string
  field?: string
}

export interface ProgressInfo {
  node_id: string
  row: number
  total_rows: number
}

export interface ExecutionResult {
  success: boolean
  errors: unknown[]
  node_statuses: Record<string, NodeStatus>
}

export interface ExecutionStatus {
  state: 'running' | 'idle'
  last_result: ExecutionResult | null
  progress: ProgressInfo | null
}

export interface OMEROInstance {
  name?: string | null
  host: string
  port?: number
  username: string
}

export interface Settings {
  deployment_mode: 'desktop' | 'webapp'
  external_editor?: string | null
  napari_env_path?: string | null
  omero_instances?: OMEROInstance[]
  output_data_folder: string
  tool_store_path?: string
  update_mode?: string
  execution_engine?: 'sequential' | 'parsl'
  cache_max_executions?: number | null
  cache_max_age?: string | null
  keyboard_shortcuts?: Record<string, string>
  dev_mode?: boolean
}
