import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

import { api } from '@/api/client'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'
import type { ExecutionSnapshot } from '@/api/executions'

const actions = {
  cancel: { available: false, reason: 'terminal' },
  retry: { available: true, reason: null },
  recompute: { available: true, reason: null },
  download_results: { available: false, reason: 'not succeeded' },
}

function snapshot(revision: number, state: ExecutionSnapshot['state']): ExecutionSnapshot {
  return {
    id: 'run-1', revision, workflow_id: 'workflow', target_id: 'cluster',
    target_mode: 'submitted_remote', state, created_at: '2026-08-03T10:00:00Z',
    child_execution_ids: [], actions, jobs: [],
  }
}

function snapshotWire(revision: number, state: ExecutionSnapshot['state'], id = 'run-1') {
  return {
    revision,
    execution_id: id,
    workflow_id: 'workflow',
    backend: 'submitted_remote',
    target_id: 'cluster',
    state,
    retry_of_execution_id: null,
    child_execution_ids: [],
    actions,
    jobs: {},
    created_at: '2026-08-03T10:00:00Z',
  }
}

describe('execution registry store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
  })

  it('surfaces capability discovery failures without a legacy target fallback', async () => {
    vi.mocked(api.get).mockRejectedValueOnce(new Error('capability discovery failed'))
    const store = useExecutionRegistryStore()

    await store.loadTargets()

    expect(store.targets).toEqual([])
    expect(store.selectedTarget).toBeNull()
    expect(store.error).toBe('capability discovery failed')
  })

  it('applies only monotonically newer snapshots', () => {
    const store = useExecutionRegistryStore()
    store.applySnapshot(snapshot(4, 'running'))
    store.applySnapshot(snapshot(3, 'failed'))

    expect(store.runs[0]).toMatchObject({ revision: 4, state: 'running' })
    expect(store.activeRuns).toHaveLength(1)

    store.applySnapshot(snapshot(5, 'succeeded'))
    expect(store.runs[0]).toMatchObject({ revision: 5, state: 'succeeded' })
    expect(store.activeRuns).toHaveLength(0)
  })

  it('keeps cancellation and persisted retry plans scoped to the parent run', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: snapshotWire(2, 'cancel_requested'),
    })
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: { execution_id: 'run-1', state: 'cancel_requested' } })
      .mockResolvedValueOnce({ data: {
        plan_digest: 'sha256:plan', parent_execution_id: 'run-1',
        child_execution_id: 'run-2', mode: 'retry',
        target: { id: 'cluster', label: 'Cluster', mode: 'submitted_remote' },
        recompute: null, invalidations: [], conflicting_run_ids: [], confirmable: true,
      } })
      .mockResolvedValueOnce({ data: {
        ...snapshotWire(1, 'prepared', 'run-2'),
        retry_of_execution_id: 'run-1',
      } })
    const store = useExecutionRegistryStore()
    store.applySnapshot(snapshot(1, 'running'))

    await store.cancel('run-1')
    const plan = await store.planRetry('run-1', null)
    await store.startRetry('run-1', plan.plan_digest)

    expect(vi.mocked(api.post).mock.calls.map(call => call[0])).toEqual([
      '/api/v1/executions/run-1/cancel',
      '/api/v1/executions/run-1/retry/plan',
      '/api/v1/executions/run-1/retry',
    ])
    expect(vi.mocked(api.post).mock.calls[2]?.[1]).toEqual({ plan_digest: 'sha256:plan' })
    expect(store.selectedRunId).toBe('run-2')
  })

  it('loads retained history with backend offset pagination', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: {
        items: [snapshotWire(1, 'succeeded', 'run-1')], total: 3, offset: 0, limit: 1,
      } })
      .mockResolvedValueOnce({ data: {
        items: [snapshotWire(1, 'failed', 'run-2')], total: 3, offset: 1, limit: 1,
      } })
    const store = useExecutionRegistryStore()

    await store.loadRuns('workflow')
    store.applySnapshot({ ...snapshot(1, 'running'), id: 'run-live' })
    await store.loadMoreRuns()

    expect(vi.mocked(api.get).mock.calls.map(call => call[1]?.params)).toEqual([
      { workflow_id: 'workflow', offset: 0, limit: 50 },
      { workflow_id: 'workflow', offset: 1, limit: 1 },
    ])
    expect(store.runs.map(run => run.id)).toEqual(['run-live', 'run-1', 'run-2'])
    expect(store.totalRuns).toBe(3)
    expect(store.hasMoreRuns).toBe(true)
  })
})
