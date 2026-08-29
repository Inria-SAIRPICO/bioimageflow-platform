import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { api } from '@/api/client'
import {
  applyClusterCleanup,
  createExecutionProfile,
  describeExecutionProfile,
  downloadSlurmProfileExample,
  listExecutionProfiles,
  planClusterCleanup,
  updateExecutionProfile,
  type ExecutionProfile,
} from '@/api/executionProfiles'

const profile: ExecutionProfile = {
  schema: 'bioimageflow.platform.execution-profile.v2',
  id: 'site-cluster',
  revision: 1,
  name: 'Site cluster',
  enabled: true,
  editable: true,
  config_path: '/site/cluster.py',
  config_digest: 'sha256:config',
  cluster_host: 'login.cluster',
  cluster_root: '/cluster/workflows',
}

describe('managed execution profile API', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
    vi.mocked(api.patch).mockReset()
    vi.mocked(api.delete).mockReset()
  })

  it('keeps the persisted profile to one trusted script and non-secret identities', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: {
      editable: false,
      profiles: [{ ...profile, editable: undefined }],
    } })
    vi.mocked(api.post).mockResolvedValueOnce({ data: profile })
    vi.mocked(api.patch).mockResolvedValueOnce({ data: { ...profile, revision: 2 } })

    const listed = await listExecutionProfiles()
    await createExecutionProfile({
      name: 'Site cluster', enabled: true, config_path: '/site/cluster.py',
    })
    await updateExecutionProfile(profile, { enabled: false })

    expect(listed[0]).toMatchObject({ editable: false, cluster_host: 'login.cluster' })
    expect(vi.mocked(api.post).mock.calls[0]?.[1]).toEqual({
      name: 'Site cluster', enabled: true, config_path: '/site/cluster.py',
    })
    expect(vi.mocked(api.patch).mock.calls[0]?.[1]).toEqual({
      expected_revision: 1,
      profile: { name: 'Site cluster', enabled: false, config_path: '/site/cluster.py' },
    })
  })

  it('describes capabilities, downloads the example, and applies an exact cleanup plan', async () => {
    const description = {
      profile_id: profile.id, profile_revision: 1, config_digest: profile.config_digest,
      cluster_host: profile.cluster_host, cluster_root: profile.cluster_root, configured: true,
      cluster: { host: profile.cluster_host, root: profile.cluster_root },
      capabilities: {
        schema: 'bioimageflow.cluster.capabilities.v1',
        capabilities: { managed_setup_scripts: { supported: true, reason: null } },
      },
      connection: { reachable: true, message: null }, diagnostics: [],
    }
    const archive = new Blob(['example'])
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: description })
      .mockResolvedValueOnce({ data: {
        profile_id: profile.id, plan_digest: 'sha256:cleanup', plan: { run_ids: ['run-1'] },
      } })
      .mockResolvedValueOnce({ data: { profile_id: profile.id, report: { removed: 1 } } })
    vi.mocked(api.get).mockResolvedValueOnce({ data: archive })

    await expect(describeExecutionProfile(profile, true)).resolves.toEqual(description)
    await expect(downloadSlurmProfileExample()).resolves.toBe(archive)
    const plan = await planClusterCleanup(profile.id, ['run-1'])
    await applyClusterCleanup(profile.id, plan.plan_digest)

    expect(vi.mocked(api.post).mock.calls.map(call => call[0])).toEqual([
      '/api/v1/execution/profiles/site-cluster/describe',
      '/api/v1/execution/profiles/site-cluster/cleanup/plan',
      '/api/v1/execution/profiles/site-cluster/cleanup',
    ])
    expect(vi.mocked(api.post).mock.calls[0]?.[2]).toEqual({
      params: { check_connection: true },
    })
    expect(vi.mocked(api.post).mock.calls[2]?.[1]).toEqual({ plan_digest: 'sha256:cleanup' })
  })
})
