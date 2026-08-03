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
  value_shape: 'path' | 'list' | 'tuple'
  values: Array<string | null>
  nullable?: boolean
  path_picker?: string | null
  cluster_compatible?: boolean
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
  profile_revision: number
  command: { kind: string; nodes?: string[]; retry_of?: string }
  node_path_resolutions?: RemoteNodePathResolution[]
}

interface RemoteNodePathPlanWire {
  inputs: Array<{
    scoped_node_path: string
    input_name: string
    value_shape: RemoteNodePathInput['value_shape']
    nullable: boolean
    path_picker: string | null
    current_paths: string[]
    cluster_compatible: boolean
  }>
}

interface ExecutionPreflightWireResponse {
  kind: 'resolution_required' | 'ready'
  distributed_plan: Record<string, unknown>
  remote_node_paths?: RemoteNodePathPlanWire
  unresolved?: Array<{ scoped_node_path: string; input_name: string }>
  token?: string | null
  expires_at?: number | null
  manifest?: {
    bundle_digest: string
    entries: Array<{ path: string; kind: 'file' | 'directory'; size: number; digest: string }>
    external_sources: Array<{
      kind: 'cluster_pre_launch'
      path: string
      expected_digest: string | null
    }>
  } | null
}

interface ExecutionSnapshotWire {
  revision: number
  execution_id: string
  workflow_id: string
  draft_revision?: number | null
  command?: string
  backend: 'direct' | 'wetlands' | 'attached_parsl' | 'submitted_local' | 'submitted_remote'
  target_id: string
  target_snapshot?: Record<string, unknown>
  state: ExecutionRunState
  jobs: Record<string, {
    scoped_node_path: string
    state: ExecutionJobState
    row?: number
    total_rows?: number
    current?: number | null
    maximum?: number | null
    message?: string | null
    result_key?: string | null
    record_id?: string | null
    executor_label?: string | null
    route_reason?: string | null
    effective_resources?: Record<string, unknown> | null
    diagnostic?: NodeFailureDiagnostic | null
    started_at?: string | null
    finished_at?: string | null
  }>
  backend_metadata?: Record<string, unknown>
  observation?: { error?: string | null }
  created_at: string
  finished_at?: string | null
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
  const { data } = await api.get<{
    targets: Array<{
      id: string
      name: string
      mode: ExecutionTargetMode
      available: boolean
      disabled_reason?: string | null
      profile_revision?: number | null
    }>
  }>(
    '/api/v1/execution/targets',
  )
  return data.targets.map(target => ({
    id: target.id,
    label: target.name,
    mode: target.mode,
    enabled: target.available,
    disabled_reason: target.disabled_reason,
    profile_revision: target.profile_revision,
  }))
}

export async function preflightExecution(
  request: ExecutionPreflightRequest,
): Promise<ExecutionPreflightResponse> {
  const choices: Record<string, Record<string, unknown>> = {}
  for (const resolution of request.node_path_resolutions ?? []) {
    choices[resolution.node_path] ??= {}
    choices[resolution.node_path]![resolution.input_name] = resolution.value_shape === 'path'
      ? encodeRemoteLeaf(resolution.values[0]!)
      : resolution.values.map(encodeRemoteLeaf)
  }
  const { data } = await api.post<ExecutionPreflightWireResponse>(
    '/api/v1/execution/preflight',
    {
      workflow_id: request.workflow_id,
      draft_revision: request.draft_revision,
      target_id: request.target_id,
      profile_revision: request.profile_revision,
      requested_nodes: request.command.nodes ?? null,
      node_path_choices: choices,
    },
  )
  if (data.kind === 'resolution_required') {
    const unresolvedKeys = new Set((data.unresolved ?? []).map(item => (
      `${item.scoped_node_path}\n${item.input_name}`
    )))
    return {
      status: 'resolution_required',
      unresolved_paths: (data.remote_node_paths?.inputs ?? [])
        .filter(item => unresolvedKeys.has(`${item.scoped_node_path}\n${item.input_name}`))
        .map(item => ({
          node_path: item.scoped_node_path,
          input_name: item.input_name,
          value_shape: item.value_shape,
          values: item.value_shape === 'path' && item.current_paths.length === 0
            ? [null]
            : item.current_paths,
          nullable: item.nullable,
          path_picker: item.path_picker,
          cluster_compatible: item.cluster_compatible,
        })),
    }
  }
  if (!data.token || data.expires_at == null || !data.manifest) {
    throw new Error('This execution target cannot yet be started by the retained runtime')
  }
  const uploadEntries = data.manifest.entries.filter(entry => (
    entry.path.startsWith('uploads/')
  ))
  return {
    status: 'ready',
    token: data.token,
    expires_at: new Date(data.expires_at * 1000).toISOString(),
    manifest: {
      uploads_count: uploadEntries.length,
      total_bytes: data.manifest.entries.reduce((total, entry) => total + entry.size, 0),
      entries: [
        ...data.manifest.entries.map(entry => ({
          kind: entry.path.includes('pre-launch') ? 'pre_launch_script' as const : 'upload' as const,
          label: entry.path,
          size_bytes: entry.size,
          digest: entry.digest,
        })),
        ...data.manifest.external_sources.map(source => ({
          kind: 'pre_launch_script' as const,
          label: source.path,
          source_kind: source.kind,
          digest: source.expected_digest,
          cluster_path: source.path,
          pinned: source.expected_digest !== null,
        })),
      ],
    },
  }
}

function encodeRemoteLeaf(leaf: RemoteNodePathLeaf): { source: string; value: string | null } {
  return {
    source: leaf.source,
    value: leaf.source === 'none' ? null : leaf.path,
  }
}

function targetMode(backend: ExecutionSnapshotWire['backend']): ExecutionTargetMode {
  if (backend === 'submitted_local' || backend === 'submitted_remote') return backend
  if (backend === 'attached_parsl') return 'attached'
  return 'local'
}

function secondsBetween(start?: string | null, finish?: string | null): number | null {
  if (!start || !finish) return null
  return Math.max(0, (Date.parse(finish) - Date.parse(start)) / 1000)
}

export function normalizeExecution(data: ExecutionSnapshotWire): ExecutionSnapshot {
  const targetLabel = typeof data.target_snapshot?.name === 'string'
    ? data.target_snapshot.name
    : null
  return {
    id: data.execution_id,
    revision: data.revision,
    workflow_id: data.workflow_id,
    draft_revision: data.draft_revision,
    target_id: data.target_id,
    target_label: targetLabel,
    target_mode: targetMode(data.backend),
    state: data.state,
    command: data.command,
    created_at: data.created_at,
    finished_at: data.finished_at,
    backend_id: data.backend,
    scheduler_job_id: typeof data.backend_metadata?.scheduler_job_id === 'string'
      ? data.backend_metadata.scheduler_job_id
      : null,
    observation_error: data.observation?.error,
    jobs: Object.values(data.jobs).map(job => ({
      id: job.scoped_node_path,
      scoped_node_path: job.scoped_node_path,
      state: job.state,
      progress: job.current != null && job.maximum != null
        ? { current: job.current, total: job.maximum, label: job.message }
        : job.total_rows != null && job.total_rows > 0
          ? { current: job.row ?? 0, total: job.total_rows, label: job.message }
          : null,
      executor_label: job.executor_label,
      resources: job.effective_resources as ExecutionResources | null | undefined,
      route_reason: job.route_reason,
      started_at: job.started_at,
      finished_at: job.finished_at,
      duration_seconds: secondsBetween(job.started_at, job.finished_at),
      diagnostic: job.diagnostic,
      result_key: job.result_key,
      record_id: job.record_id,
    })),
  }
}

export async function applyPreparedExecution(
  token: string,
  request: ExecutionPreflightRequest,
): Promise<ExecutionSnapshot> {
  const { data } = await api.post<ExecutionSnapshotWire>(
    '/api/v1/executions',
    {
      token,
      workflow_id: request.workflow_id,
      draft_revision: request.draft_revision,
      target_id: request.target_id,
      requested_nodes: request.command.nodes ?? null,
    },
  )
  return normalizeExecution(data)
}

export async function fetchExecutions(options: {
  workflowId?: string | null
  cursor?: string | null
} = {}): Promise<ExecutionPage> {
  const { data } = await api.get<{ items: ExecutionSnapshotWire[] }>('/api/v1/executions', {
    params: {
      ...(options.workflowId ? { workflow_id: options.workflowId } : {}),
      ...(options.cursor ? { cursor: options.cursor } : {}),
    },
  })
  return { items: data.items.map(normalizeExecution) }
}

export async function fetchExecution(id: string): Promise<ExecutionSnapshot> {
  const { data } = await api.get<ExecutionSnapshotWire>(
    `/api/v1/executions/${encodeURIComponent(id)}`,
  )
  return normalizeExecution(data)
}

export async function cancelExecution(id: string): Promise<ExecutionSnapshot> {
  await api.post(
    `/api/v1/executions/${encodeURIComponent(id)}/cancel`,
  )
  return fetchExecution(id)
}

export async function retryExecution(id: string): Promise<ExecutionSnapshot> {
  const { data } = await api.post<ExecutionSnapshotWire>(
    `/api/v1/executions/${encodeURIComponent(id)}/retry`,
    {},
  )
  return normalizeExecution(data)
}

export async function downloadExecutionResults(id: string): Promise<Blob> {
  const response = await api.post(
    `/api/v1/executions/${encodeURIComponent(id)}/result`,
    { destination: 'download' },
    { responseType: 'blob' },
  )
  return response.data as Blob
}
