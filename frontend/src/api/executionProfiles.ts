import { api } from '@/api/client'
import type {
  DistributedExecutionProfile,
  ExecutionProfileCreate,
  ExecutionProfileDescription,
  ExecutionProfileList,
  ExecutionProfilePatch,
} from '@/api/types'

export type ExecutionProfile = DistributedExecutionProfile & {
  editable: boolean
}

export type ExecutionProfileDraft = ExecutionProfileCreate

export type ProfileDescription = ExecutionProfileDescription
export type ClusterDiagnostic = NonNullable<ExecutionProfileDescription['diagnostics']>[number]

function withEditable(profile: DistributedExecutionProfile, editable: boolean): ExecutionProfile {
  return { ...profile, editable }
}

export async function listExecutionProfiles(): Promise<ExecutionProfile[]> {
  const { data } = await api.get<ExecutionProfileList>('/api/v1/execution/profiles')
  return data.profiles.map(profile => withEditable(profile, data.editable))
}

export async function createExecutionProfile(
  profile: ExecutionProfileDraft,
): Promise<ExecutionProfile> {
  const { data } = await api.post<DistributedExecutionProfile>(
    '/api/v1/execution/profiles',
    profile,
  )
  return withEditable(data, true)
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
  const body: ExecutionProfilePatch = {
    expected_revision: profile.revision,
    profile: fields,
  }
  const { data } = await api.patch<DistributedExecutionProfile>(
    `/api/v1/execution/profiles/${encodeURIComponent(profile.id)}`,
    body,
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
