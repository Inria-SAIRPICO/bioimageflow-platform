import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

import { api } from '@/api/client'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'
import type { ExecutionSnapshot } from '@/api/executions'

function snapshot(revision: number, state: ExecutionSnapshot['state']): ExecutionSnapshot {
  return {
    id: 'run-1', revision, workflow_id: 'workflow', target_id: 'cluster',
    target_mode: 'submitted_remote', state, created_at: '2026-08-03T10:00:00Z',
    jobs: [],
  }
}

describe('execution registry store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
  })

  it('retains Local when capability discovery is unavailable', async () => {
    vi.mocked(api.get).mockRejectedValueOnce(new Error('old backend'))
    const store = useExecutionRegistryStore()

    await store.loadTargets()

    expect(store.targets).toEqual([
      { id: 'local', label: 'Local', mode: 'local', enabled: true },
    ])
    expect(store.selectedTargetId).toBe('local')
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

  it('keeps cancel and retry actions scoped to the selected run ID', async () => {
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: snapshot(2, 'cancel_requested') })
      .mockResolvedValueOnce({ data: { ...snapshot(1, 'queued'), id: 'run-2' } })
    const store = useExecutionRegistryStore()
    store.applySnapshot(snapshot(1, 'running'))

    await store.cancel('run-1')
    await store.retry('run-1')

    expect(vi.mocked(api.post).mock.calls.map(call => call[0])).toEqual([
      '/api/v1/executions/run-1/cancel',
      '/api/v1/executions/run-1/retry',
    ])
    expect(store.selectedRunId).toBe('run-2')
  })
})
