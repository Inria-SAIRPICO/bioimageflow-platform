import { api } from '@/api/client'

export type ExecutionTargetMode =
  | 'local'
  | 'attached'
  | 'submitted_local'
  | 'submitted_remote'

export interface ExecutionTarget {
  id: string
  label: string
  mode: ExecutionTargetMode
  enabled: boolean
  disabled_reason?: string | null
  profile_revision?: number | null
}

export type ExecutionRunState =
  | 'preparing'
  | 'prepared'
  | 'queued'
  | 'starting'
  | 'running'
  | 'cancel_requested'
  | 'finalizing'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'lost'

export type ExecutionJobState =
  | 'waiting'
  | 'running'
  | 'cached'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'skipped'
  | 'blocked'

export interface ExecutionResources {
  cpu?: number | null
  gpu?: number | null
  memory_gb?: number | null
  gpu_memory_gb?: number | null
  max_concurrent?: number | null
}

export interface NodeFailureDiagnostic {
  category?: string | null
  exception_type?: string | null
  message: string
  traceback?: string | null
  terminal?: boolean
  attempt_id?: string | null
}

export interface ExecutionJobSnapshot {
  id: string
  scoped_node_path: string
  display_name?: string | null
  parent_path?: string | null
  state: ExecutionJobState
  progress?: { current: number; total: number; label?: string | null } | null
  executor_label?: string | null
  resources?: ExecutionResources | null
  route_reason?: string | null
  started_at?: string | null
  finished_at?: string | null
  duration_seconds?: number | null
  diagnostic?: NodeFailureDiagnostic | null
  result_key?: string | null
  record_id?: string | null
}

export interface ExecutionSnapshot {
  id: string
  revision: number
  workflow_id: string
  workflow_name?: string | null
  draft_revision?: number | null
  target_id: string
  target_label?: string | null
  target_mode: ExecutionTargetMode
  state: ExecutionRunState
  command?: string | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  backend_id?: string | null
  scheduler_job_id?: string | null
  observation_error?: string | null
  jobs: ExecutionJobSnapshot[]
}

export interface RemoteNodePathInput {
  node_path: string
  input_name: string
  value_shape: 'scalar' | 'list' | 'tuple'
  values: Array<string | null>
  nullable?: boolean
}

export type RemoteNodePathLeaf =
  | { source: 'upload'; path: string; dataset_id?: string }
  | { source: 'cluster'; path: string }
  | { source: 'none' }

export interface RemoteNodePathResolution {
  node_path: string
  input_name: string
  value_shape: RemoteNodePathInput['value_shape']
  values: RemoteNodePathLeaf[]
}

export interface PreparedManifestEntry {
  kind: 'upload' | 'cluster_path' | 'pre_launch_script'
  label: string
  source_kind?: string | null
  size_bytes?: number | null
  file_count?: number | null
  digest?: string | null
  cluster_path?: string | null
  pinned?: boolean | null
}

export interface PreparedManifest {
  uploads_count: number
  total_bytes: number
  entries: PreparedManifestEntry[]
}

export interface ExecutionPreflightRequest {
  workflow_id: string
  draft_revision: number | null
  graph: unknown
  target_id: string
  command: { kind: string; nodes?: string[]; retry_of?: string }
  node_path_resolutions?: RemoteNodePathResolution[]
}

export type ExecutionPreflightResponse =
  | {
      status: 'resolution_required'
      unresolved_paths: RemoteNodePathInput[]
      routing_choices?: unknown[]
    }
  | {
      status: 'ready'
      token: string
      expires_at: string
      manifest: PreparedManifest
      plan_summary?: { scheduled_jobs?: number; cached_jobs?: number }
      warnings?: string[]
    }

export interface ExecutionPage {
  items: ExecutionSnapshot[]
  next_cursor?: string | null
}

export async function fetchExecutionTargets(): Promise<ExecutionTarget[]> {
  const { data } = await api.get<{ targets: ExecutionTarget[] } | ExecutionTarget[]>(
    '/api/v1/execution/targets',
  )
  return Array.isArray(data) ? data : data.targets
}

export async function preflightExecution(
  request: ExecutionPreflightRequest,
): Promise<ExecutionPreflightResponse> {
  const { data } = await api.post<ExecutionPreflightResponse>(
    '/api/v1/execution/preflight',
    request,
  )
  return data
}

export async function applyPreparedExecution(token: string): Promise<ExecutionSnapshot> {
  const { data } = await api.post<ExecutionSnapshot>(
    '/api/v1/executions',
    { preflight_token: token },
  )
  return data
}

export async function fetchExecutions(options: {
  workflowId?: string | null
  cursor?: string | null
} = {}): Promise<ExecutionPage> {
  const { data } = await api.get<ExecutionPage>('/api/v1/executions', {
    params: {
      ...(options.workflowId ? { workflow_id: options.workflowId } : {}),
      ...(options.cursor ? { cursor: options.cursor } : {}),
    },
  })
  return data
}

export async function fetchExecution(id: string): Promise<ExecutionSnapshot> {
  const { data } = await api.get<ExecutionSnapshot>(
    `/api/v1/executions/${encodeURIComponent(id)}`,
  )
  return data
}

export async function cancelExecution(id: string): Promise<ExecutionSnapshot> {
  const { data } = await api.post<ExecutionSnapshot>(
    `/api/v1/executions/${encodeURIComponent(id)}/cancel`,
  )
  return data
}

export async function retryExecution(id: string): Promise<ExecutionSnapshot> {
  const { data } = await api.post<ExecutionSnapshot>(
    `/api/v1/executions/${encodeURIComponent(id)}/retry`,
  )
  return data
}

export function executionResultsUrl(id: string): string {
  return `/api/v1/executions/${encodeURIComponent(id)}/results`
}
