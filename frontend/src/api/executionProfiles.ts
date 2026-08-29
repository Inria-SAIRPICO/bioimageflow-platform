import { api } from '@/api/client'

export interface ExecutionProfile {
  schema: 'bioimageflow.platform.execution-profile.v2'
  id: string
  revision: number
  name: string
  enabled: boolean
  editable: boolean
  config_path: string
  config_digest: string
  cluster_host: string
  cluster_root: string
}

export interface ExecutionProfileDraft {
  name: string
  enabled: boolean
  config_path: string
}

export interface CapabilityStatus {
  supported: boolean
  reason?: string | null
}

export interface ClusterDiagnostic {
  schema?: string
  phase: string
  category: string
  message: string
  allocation_state?: string | null
  retry_safety?: string | null
  next_action?: string | null
  identities?: Record<string, string | null>
}

export interface ProfileDescription {
  profile_id: string
  profile_revision: number
  config_digest: string
  cluster_host: string
  cluster_root: string
  configured: boolean
  cluster: Record<string, unknown>
  capabilities: {
    schema: string
    capabilities: Record<string, CapabilityStatus>
  }
  connection: Record<string, unknown> | null
  diagnostics: ClusterDiagnostic[]
}

export interface ClusterCleanupPlan {
  profile_id: string
  plan_digest: string
  plan: Record<string, unknown>
}

export interface ClusterCleanupReport {
  profile_id: string
  report: Record<string, unknown>
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
  const { data } = await api.post<Omit<ExecutionProfile, 'editable'>>(
    '/api/v1/execution/profiles',
    profile,
  )
  return withEditable(data)
}

export async function updateExecutionProfile(
  profile: ExecutionProfile,
  changes: Partial<ExecutionProfileDraft>,
): Promise<ExecutionProfile> {
  const fields: ExecutionProfileDraft = {
    name: changes.name ?? profile.name,
    enabled: changes.enabled ?? profile.enabled,
    config_path: changes.config_path ?? profile.config_path,
  }
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

export async function describeExecutionProfile(
  profile: ExecutionProfile,
  checkConnection = false,
): Promise<ProfileDescription> {
  const { data } = await api.post<ProfileDescription>(
    `/api/v1/execution/profiles/${encodeURIComponent(profile.id)}/describe`,
    undefined,
    { params: { check_connection: checkConnection } },
  )
  return data
}

export async function downloadSlurmProfileExample(): Promise<Blob> {
  const { data } = await api.get<Blob>('/api/v1/execution/profiles/example/slurm', {
    responseType: 'blob',
  })
  return data
}

export async function planClusterCleanup(
  profileId: string,
  runIds: string[],
): Promise<ClusterCleanupPlan> {
  const { data } = await api.post<ClusterCleanupPlan>(
    `/api/v1/execution/profiles/${encodeURIComponent(profileId)}/cleanup/plan`,
    { run_ids: runIds, older_than_seconds: 0 },
  )
  return data
}

export async function applyClusterCleanup(
  profileId: string,
  planDigest: string,
): Promise<ClusterCleanupReport> {
  const { data } = await api.post<ClusterCleanupReport>(
    `/api/v1/execution/profiles/${encodeURIComponent(profileId)}/cleanup`,
    { plan_digest: planDigest },
  )
  return data
}
