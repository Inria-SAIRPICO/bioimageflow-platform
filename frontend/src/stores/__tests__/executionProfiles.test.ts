import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/executionProfiles', async importOriginal => {
  const original = await importOriginal<typeof import('@/api/executionProfiles')>()
  return {
    ...original,
    listExecutionProfiles: vi.fn(),
    createExecutionProfile: vi.fn(),
    updateExecutionProfile: vi.fn(),
    deleteExecutionProfile: vi.fn(),
    describeExecutionProfile: vi.fn(),
  }
})

import {
  createExecutionProfile,
  deleteExecutionProfile,
  describeExecutionProfile,
  listExecutionProfiles,
  updateExecutionProfile,
  type ExecutionProfile,
} from '@/api/executionProfiles'
import { useExecutionProfilesStore } from '../executionProfiles'
import { campaignExcluded } from '@/test-utils/campaignVitest'

const excluded = campaignExcluded('managed-remote')

const profile: ExecutionProfile = {
  schema: 'bioimageflow.platform.execution-profile.v2',
  id: 'cluster',
  revision: 1,
  name: 'Cluster',
  enabled: true,
  editable: true,
  config_path: '/site/cluster.py',
  config_digest: 'sha256:config',
  cluster_host: 'login.cluster',
  cluster_root: '/cluster/workflows',
}

describe('execution profiles store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  excluded('loads, revises, describes, and removes profiles by immutable identity', async () => {
    vi.mocked(listExecutionProfiles).mockResolvedValue([profile])
    vi.mocked(updateExecutionProfile).mockResolvedValue({ ...profile, revision: 2 })
    vi.mocked(describeExecutionProfile).mockResolvedValue({
      profile_id: 'cluster',
      profile_revision: 2,
      config_digest: 'sha256:config',
      cluster_host: 'login.cluster',
      cluster_root: '/cluster/workflows',
      configured: true,
      cluster: {
        schema: 'bioimageflow.remote_cluster.v1',
        host: 'login.cluster',
        root: '/cluster/workflows',
        configured: true,
      },
      capabilities: { schema: 'bioimageflow.execution_capabilities.v1', capabilities: {} },
      connection: null,
      diagnostics: [],
    })
    vi.mocked(deleteExecutionProfile).mockResolvedValue()

    const store = useExecutionProfilesStore()
    await store.refresh()
    expect(store.enabled).toEqual([profile])

    await store.update(profile, { name: 'Revised cluster' })
    expect(store.profiles[0]?.revision).toBe(2)
    expect(await store.describe(store.profiles[0]!)).toMatchObject({
      configured: true,
      cluster_host: 'login.cluster',
    })
    await store.remove(store.profiles[0]!)
    expect(store.profiles).toEqual([])
  })

  excluded('adds a profile returned by the server', async () => {
    vi.mocked(createExecutionProfile).mockResolvedValue(profile)
    const store = useExecutionProfilesStore()
    const draft = { name: profile.name, enabled: profile.enabled, config_path: profile.config_path }
    await store.create(draft)
    expect(store.profiles).toEqual([profile])
  })
})
