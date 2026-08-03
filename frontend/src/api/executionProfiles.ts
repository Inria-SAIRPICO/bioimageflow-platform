import { api } from '@/api/client'

export type ExecutionProfileMode = 'attached' | 'submitted_local' | 'submitted_remote'

export type PreLaunchSource =
  | { kind: 'inline'; text: string }
  | { kind: 'local_file'; path: string }
  | { kind: 'cluster_file'; path: string; expected_digest: string | null }
  | null

export interface ExecutionProfile {
  schema: 'bioimageflow.platform.execution-profile.v1'
  id: string
  revision: number
  name: string
  enabled: boolean
  editable: boolean
  mode: ExecutionProfileMode
  parsl_config: {
    factory: string
    kwargs: Record<string, unknown>
    secret_refs: Record<string, string> | null
  }
  executor_bindings: Record<string, unknown>
  environment_routes: Record<string, string>
  shared_runtime_root: string | null
  task_policy: Record<string, unknown>
  launch: Record<string, unknown> | null
  transport: Record<string, unknown> | null
  remote_workflow_root: string | null
  pre_launch: PreLaunchSource
}

export type ExecutionProfileDraft = Omit<ExecutionProfile, 'id' | 'revision' | 'editable'>

export interface ProfileValidationResult {
  valid: boolean
  diagnostics: Array<{ code: string; message: string }>
  allocation_created?: boolean
  workflow_run_created?: boolean
  pre_launch_executed?: boolean
}

interface ExecutionProfileListResponse {
  editable: boolean
  profiles: Array<Omit<ExecutionProfile, 'editable'> & { editable?: boolean }>
}

function withEditable(
  profile: Omit<ExecutionProfile, 'editable'> & { editable?: boolean },
  fallback = true,
): ExecutionProfile {
  return { ...profile, editable: profile.editable ?? fallback }
}

export async function listExecutionProfiles(): Promise<ExecutionProfile[]> {
  const { data } = await api.get<ExecutionProfileListResponse>('/api/v1/execution/profiles')
  return data.profiles.map(profile => withEditable(profile, data.editable))
}

export async function createExecutionProfile(
  profile: ExecutionProfileDraft,
): Promise<ExecutionProfile> {
  const { schema: _schema, ...fields } = profile
  const { data } = await api.post<Omit<ExecutionProfile, 'editable'>>(
    '/api/v1/execution/profiles',
    fields,
  )
  return withEditable(data)
}

export async function updateExecutionProfile(
  profile: ExecutionProfile,
  changes: Partial<ExecutionProfileDraft>,
): Promise<ExecutionProfile> {
  const {
    schema: _schema,
    id: _id,
    revision: _revision,
    editable: _editable,
    ...fields
  } = { ...profile, ...changes }
  const { data } = await api.patch<Omit<ExecutionProfile, 'editable'>>(
    `/api/v1/execution/profiles/${encodeURIComponent(profile.id)}`,
    { expected_revision: profile.revision, profile: fields },
  )
  return withEditable(data, profile.editable)
}

export async function deleteExecutionProfile(profile: ExecutionProfile): Promise<void> {
  await api.delete(`/api/v1/execution/profiles/${encodeURIComponent(profile.id)}`, {
    params: { expected_revision: profile.revision },
  })
}

export async function testExecutionProfile(
  profile: ExecutionProfile,
): Promise<ProfileValidationResult> {
  const { data } = await api.post<{
    report: ProfileValidationResult
  }>(
    `/api/v1/execution/profiles/${encodeURIComponent(profile.id)}/test`,
  )
  return data.report
}
