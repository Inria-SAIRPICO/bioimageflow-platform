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
  optional?: boolean
  min?: number
  max?: number
  step?: number
  group?: string
  choices?: string[] | null
}

export interface OutputFieldSchema {
  type: string
  default?: string
}

export interface ToolMetadata {
  name: string
  display_name: string
  package: string
  package_version: string
  tool_type: string
  documentation: string
  tags: string[]
  categories: string[]
  inputs: Record<string, InputFieldSchema>
  outputs: Record<string, OutputFieldSchema>
  environment: Record<string, unknown> | null
}

export interface PackageInfo {
  name: string
  installed_versions: string[]
  available_versions: string[]
  tools: Record<string, string[]>
  environment_status: string
}

export interface NodeState {
  id: string
  name: string
  tool_name: string
  position: [number, number]
  parameters: Record<string, unknown>
  resources?: Record<string, unknown>
  output_templates?: Record<string, string>
  enabled?: boolean
  collapsed?: boolean
}

export interface ColumnRefEdge {
  type: 'column_ref'
  id: string
  source_node: string
  target_node: string
  source_output: string
  target_input: string
}

export interface PositionalEdge {
  type: 'positional'
  id: string
  source_node: string
  target_node: string
  positional_index: number
}

export type Edge = ColumnRefEdge | PositionalEdge

export interface GraphState {
  nodes: NodeState[]
  edges: Edge[]
}

export interface NodeStatus {
  node_id: string
  status: 'unexecuted' | 'executed' | 'out_of_date' | 'disabled' | 'running' | 'failed'
  cached: boolean
  error?: string | null
  traceback?: string | null
}

export interface GraphValidationError {
  type: 'cycle_detected' | 'type_incompatible' | 'parameter_invalid' | 'missing_tool' | 'missing_connection' | 'missing_package' | 'invalid_node_id' | 'invalid_edge_id'
  detail: string
  node?: string | null
  edge_id?: string | null
  field?: string | null
}

export interface ValidationResult {
  valid: boolean
  node_statuses?: Record<string, NodeStatus>
  errors?: GraphValidationError[]
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

export interface Dataset {
  id: string
  original_filename: string
  path: string
  size: number
  upload_date: string
  content_type: string | null
}

export interface UploadedFile {
  id: string
  original_filename: string
  path: string
  size: number
  upload_date: string
  content_type: string | null
}

export interface UploadError {
  filename: string
  error: string
  detail: string
}

export interface UploadResponse {
  uploaded: UploadedFile[]
  errors: UploadError[]
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
