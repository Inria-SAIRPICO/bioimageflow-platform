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
    testExecutionProfile: vi.fn(),
  }
})

import {
  createExecutionProfile,
  deleteExecutionProfile,
  listExecutionProfiles,
  testExecutionProfile,
  updateExecutionProfile,
  type ExecutionProfile,
} from '@/api/executionProfiles'
import { useExecutionProfilesStore } from '../executionProfiles'

const profile: ExecutionProfile = {
  schema: 'bioimageflow.platform.execution-profile.v1',
  id: 'cluster',
  revision: 1,
  name: 'Cluster',
  enabled: true,
  editable: true,
  mode: 'submitted_remote',
  parsl_config: { factory: 'site:config', kwargs: {}, secret_refs: null },
  executor_bindings: {},
  environment_routes: {},
  shared_runtime_root: null,
  task_policy: {},
  launch: {},
  transport: {},
  remote_workflow_root: '/cluster/workflows',
  pre_launch: { kind: 'inline', text: 'module load python' },
}

describe('execution profiles store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('loads, revises, tests, and removes profiles by immutable identity', async () => {
    vi.mocked(listExecutionProfiles).mockResolvedValue([profile])
    vi.mocked(updateExecutionProfile).mockResolvedValue({ ...profile, revision: 2 })
    vi.mocked(testExecutionProfile).mockResolvedValue({
      valid: true,
      diagnostics: [],
      pre_launch_executed: false,
    })
    vi.mocked(deleteExecutionProfile).mockResolvedValue()

    const store = useExecutionProfilesStore()
    await store.refresh()
    expect(store.enabled).toEqual([profile])

    await store.update(profile, { name: 'Revised cluster' })
    expect(store.profiles[0]?.revision).toBe(2)
    expect(await store.test(store.profiles[0]!)).toMatchObject({
      valid: true,
      pre_launch_executed: false,
    })
    await store.remove(store.profiles[0]!)
    expect(store.profiles).toEqual([])
  })

  it('adds a profile returned by the server', async () => {
    vi.mocked(createExecutionProfile).mockResolvedValue(profile)
    const store = useExecutionProfilesStore()
    const { id: _id, revision: _revision, editable: _editable, ...draft } = profile
    await store.create(draft)
    expect(store.profiles).toEqual([profile])
  })
})
