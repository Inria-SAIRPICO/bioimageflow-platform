import { api } from '@/api/client'
import type { ClusterDiagnostic } from '@/api/executionProfiles'

export type ExecutionTargetMode = 'local' | 'managed_remote'
export type ExecutionBackend = 'direct' | 'wetlands' | 'managed_remote'

export interface ExecutionTarget {
  id: string
  label: string
  mode: ExecutionTargetMode
  enabled: boolean
  disabled_reason?: string | null
  profile_revision?: number | null
}

export interface ExecutionCapabilityStatus {
  supported: boolean
  reason?: string | null
}

export interface ExecutionCapabilities {
  schema: string
  capabilities: Record<string, ExecutionCapabilityStatus>
}

export interface ExecutionTargets {
  targets: ExecutionTarget[]
  capabilities: ExecutionCapabilities
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
  memory_bytes?: number | null
  gpu_memory_bytes?: number | null
  max_concurrent?: number | null
}

export interface ExecutionActionAvailability {
  available: boolean
  reason?: string | null
}

export interface ExecutionActions {
  cancel: ExecutionActionAvailability
  retry: ExecutionActionAvailability
  recompute: ExecutionActionAvailability
  download_results: ExecutionActionAvailability
  cleanup: ExecutionActionAvailability
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
  target_label: string
  target_mode: ExecutionTargetMode
  backend?: ExecutionBackend
  state: ExecutionRunState
  command?: string | null
  retry_of_execution_id?: string | null
  child_execution_ids: string[]
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  scheduler_job_id?: string | null
  progress_cursor?: number | null
  observation_error?: string | null
  diagnostics?: ClusterDiagnostic[]
  actions: ExecutionActions
  jobs: ExecutionJobSnapshot[]
}

export interface RecomputeRequest {
  node_paths: string[]
  cascade: boolean
}

export interface RetryInvalidation {
  node_path: string
  result_key: string
  record_id?: string | null
  selection_status: string
}

export interface RetryPlanTarget {
  id: string
  label: string
  mode: ExecutionTargetMode
}

export interface ExecutionRetryPlan {
  plan_digest: string
  parent_execution_id: string
  child_execution_id: string
  mode: 'retry' | 'recompute'
  target: RetryPlanTarget
  recompute: RecomputeRequest | null
  invalidations: RetryInvalidation[]
  conflicting_run_ids: string[]
  confirmable: boolean
  disabled_reason?: string | null
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
  distributed_plan?: Record<string, unknown>
  remote_node_paths?: RemoteNodePathPlanWire
  unresolved?: Array<{ scoped_node_path: string; input_name: string }>
  token?: string | null
  expires_at?: number | null
}

interface ExecutionJobWire {
  scoped_node_path: string
  state: ExecutionJobState
  current?: number | null
  maximum?: number | null
  total_rows?: number | null
  row?: number | null
  message?: string | null
  executor_label?: string | null
  effective_resources?: ExecutionResources | null
  route_reason?: string | null
  started_at?: string | null
  finished_at?: string | null
  diagnostic?: NodeFailureDiagnostic | null
  result_key?: string | null
  record_id?: string | null
}

export interface ExecutionPresentationWire {
  revision: number
  execution_id: string
  workflow_id: string
  draft_revision?: number | null
  backend: ExecutionBackend
  target_id: string
  target_label: string
  target_mode: ExecutionTargetMode
  scheduler_job_id?: string | null
  command?: string | null
  state: ExecutionRunState
  retry_of_execution_id?: string | null
  child_execution_ids?: string[]
  actions: ExecutionActions
  jobs?: Record<string, ExecutionJobWire>
  progress_cursor?: number | null
  diagnostics?: ClusterDiagnostic[]
  observation?: { reachable: boolean; error?: string | null }
  created_at: string
  started_at?: string | null
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
    }

export interface ExecutionPage {
  items: ExecutionSnapshot[]
  total: number
  offset: number
  limit: number
}

export interface ExecutionCleanupPlan {
  execution_id: string
  plan_digest: string
  plan: Record<string, unknown>
}

export interface ExecutionCleanupReport {
  execution_id: string
  report: Record<string, unknown>
}

export async function fetchExecutionTargets(): Promise<ExecutionTargets> {
  const { data } = await api.get<{
    capabilities: ExecutionCapabilities
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
  return {
    capabilities: data.capabilities,
    targets: data.targets.map(target => ({
      id: target.id,
      label: target.name,
      mode: target.mode,
      enabled: target.available,
      disabled_reason: target.disabled_reason,
      profile_revision: target.profile_revision,
    })),
  }
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
  if (!data.token || data.expires_at == null) {
    throw new Error('This execution target cannot yet be started by the retained runtime')
  }
  return {
    status: 'ready',
    token: data.token,
    expires_at: new Date(data.expires_at * 1000).toISOString(),
  }
}

function encodeRemoteLeaf(leaf: RemoteNodePathLeaf): { source: string; value: string | null } {
  return {
    source: leaf.source,
    value: leaf.source === 'none' ? null : leaf.path,
  }
}

function secondsBetween(start?: string | null, finish?: string | null): number | null {
  if (!start || !finish) return null
  return Math.max(0, (Date.parse(finish) - Date.parse(start)) / 1000)
}

export function normalizeExecution(data: ExecutionPresentationWire): ExecutionSnapshot {
  return {
    id: data.execution_id,
    revision: data.revision,
    workflow_id: data.workflow_id,
    draft_revision: data.draft_revision,
    target_id: data.target_id,
    target_label: data.target_label,
    target_mode: data.target_mode,
    backend: data.backend,
    state: data.state,
    command: data.command,
    retry_of_execution_id: data.retry_of_execution_id,
    child_execution_ids: data.child_execution_ids ?? [],
    created_at: data.created_at,
    finished_at: data.finished_at,
    scheduler_job_id: data.scheduler_job_id,
    progress_cursor: data.progress_cursor,
    observation_error: data.observation?.error,
    diagnostics: data.diagnostics ?? [],
    actions: {
      ...data.actions,
      cleanup: data.actions.cleanup ?? {
        available: false,
        reason: 'Managed cluster cleanup is unavailable for this execution.',
      },
    },
    jobs: Object.values(data.jobs ?? {}).map(job => ({
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
  const { data } = await api.post<ExecutionPresentationWire>(
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
  offset?: number
  limit?: number
} = {}): Promise<ExecutionPage> {
  const { data } = await api.get<{
    items: ExecutionPresentationWire[]
    total: number
    offset: number
    limit: number
  }>('/api/v1/executions', {
    params: {
      ...(options.workflowId ? { workflow_id: options.workflowId } : {}),
      offset: options.offset ?? 0,
      limit: options.limit ?? 50,
    },
  })
  return {
    items: data.items.map(normalizeExecution),
    total: data.total,
    offset: data.offset,
    limit: data.limit,
  }
}

export async function fetchExecution(id: string): Promise<ExecutionSnapshot> {
  const { data } = await api.get<ExecutionPresentationWire>(
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

export async function planExecutionCleanup(id: string): Promise<ExecutionCleanupPlan> {
  const { data } = await api.post<ExecutionCleanupPlan>(
    `/api/v1/executions/${encodeURIComponent(id)}/cleanup/plan`,
    { older_than_seconds: 0 },
  )
  return data
}

export async function applyExecutionCleanup(
  id: string,
  planDigest: string,
): Promise<ExecutionCleanupReport> {
  const { data } = await api.post<ExecutionCleanupReport>(
    `/api/v1/executions/${encodeURIComponent(id)}/cleanup`,
    { plan_digest: planDigest },
  )
  return data
}

export async function planExecutionRetry(
  id: string,
  recompute: RecomputeRequest | null,
): Promise<ExecutionRetryPlan> {
  const { data } = await api.post<ExecutionRetryPlan>(
    `/api/v1/executions/${encodeURIComponent(id)}/retry/plan`,
    { recompute },
  )
  return data
}

export async function startExecutionRetry(
  id: string,
  planDigest: string,
): Promise<ExecutionSnapshot> {
  const { data } = await api.post<ExecutionPresentationWire>(
    `/api/v1/executions/${encodeURIComponent(id)}/retry`,
    { plan_digest: planDigest },
  )
  return normalizeExecution(data)
}

export async function downloadExecutionResults(id: string): Promise<Blob> {
  const response = await api.post<Blob>(
    `/api/v1/executions/${encodeURIComponent(id)}/result`,
    undefined,
    { responseType: 'blob' },
  )
  return response.data
}

interface ExecutionErrorPayload {
  error?: unknown
  detail?: unknown
  details?: unknown
  message?: unknown
  identities?: unknown
}

function executionErrorPayload(cause: unknown): ExecutionErrorPayload | null {
  if (!(cause instanceof Error)) return null
  const data = (cause as Error & { response?: { data?: unknown } }).response?.data
  if (typeof data !== 'object' || data === null || data instanceof Blob) return null
  return data as ExecutionErrorPayload
}

function normalizedExecutionError(
  payload: ExecutionErrorPayload | null,
): ExecutionErrorPayload | null {
  if (!payload) return null
  const nested = payload.detail
  if (typeof nested !== 'object' || nested === null) return payload
  const candidate = nested as ExecutionErrorPayload
  if (candidate.error !== undefined || candidate.details !== undefined || candidate.detail !== undefined) {
    return candidate
  }
  return payload
}

export function executionErrorCode(cause: unknown): string | null {
  const code = normalizedExecutionError(executionErrorPayload(cause))?.error
  return typeof code === 'string' && code.length > 0 ? code : null
}

export function executionErrorDetails(cause: unknown): Record<string, unknown> {
  const payload = normalizedExecutionError(executionErrorPayload(cause))
  const details = payload?.details ?? payload?.identities
  return typeof details === 'object' && details !== null
    ? details as Record<string, unknown>
    : {}
}

export function executionErrorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof Error && cause.message) {
    const payload = normalizedExecutionError(executionErrorPayload(cause))
    const detail = payload?.detail
    if (typeof detail === 'string' && detail) return detail
    if (typeof detail === 'object' && detail !== null) {
      const message = (detail as { message?: unknown }).message
      if (typeof message === 'string' && message) return message
    }
    if (typeof payload?.message === 'string' && payload.message) return payload.message
    const code = payload?.error
    if (typeof code === 'string' && code) return code.replace(/_/g, ' ')
    return cause.message
  }
  return fallback
}

export async function executionResultErrorMessage(
  cause: unknown,
  fallback: string,
): Promise<string> {
  if (!(cause instanceof Error)) return fallback
  const response = (cause as Error & { response?: { data?: unknown } }).response
  const data = response?.data
  if (!(data instanceof Blob)) return executionErrorMessage(cause, fallback)
  try {
    const decoded = JSON.parse(await data.text()) as ExecutionErrorPayload
    const payload = normalizedExecutionError(decoded)
    if (!payload) return fallback
    if (typeof payload.detail === 'string' && payload.detail) return payload.detail
    if (typeof payload.detail === 'object' && payload.detail !== null) {
      const message = (payload.detail as { message?: unknown }).message
      if (typeof message === 'string' && message) return message
    }
    if (typeof payload.message === 'string' && payload.message) return payload.message
    if (typeof payload.error === 'string' && payload.error) {
      return payload.error.replace(/_/g, ' ')
    }
  } catch {
    // A non-JSON blob has no structured server detail to expose.
  }
  return fallback
}
