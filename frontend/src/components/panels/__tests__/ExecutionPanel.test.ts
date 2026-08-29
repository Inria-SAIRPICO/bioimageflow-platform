import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { primeVueTestGlobal } from '@/test-utils/mountFixtures'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: { items: [], total: 0, offset: 0, limit: 50 } }),
    post: vi.fn(),
  },
}))

import { api } from '@/api/client'
import ExecutionPanel from '../ExecutionPanel.vue'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'
import { useUIStore } from '@/stores/ui'

const retryActions = {
  cancel: { available: false, reason: 'Execution is terminal' },
  retry: { available: true, reason: null },
  recompute: { available: true, reason: null },
  download_results: { available: false, reason: 'Results require success' },
  cleanup: { available: true, reason: null },
}

describe('ExecutionPanel', () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset()
    vi.mocked(api.get).mockReset()
    vi.mocked(api.get).mockResolvedValue({
      data: { items: [], total: 0, offset: 0, limit: 50 },
    })
  })

  it('renders hierarchical jobs and structured diagnostics from a normalized snapshot', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const registry = useExecutionRegistryStore()
    registry.applySnapshot({
      id: 'run-1', revision: 1, workflow_id: 'workflow', workflow_name: 'Workflow',
      target_id: 'cluster', target_label: 'GPU cluster', target_mode: 'managed_remote', backend: 'managed_remote',
      state: 'failed', created_at: '2026-08-03T10:00:00Z',
      command: 'recompute', retry_of_execution_id: 'run-parent',
      child_execution_ids: [], actions: retryActions,
      jobs: [{
        id: 'job-1', scoped_node_path: 'preprocessing/segment', display_name: 'Segment',
        parent_path: 'preprocessing', state: 'failed', executor_label: 'gpu',
        resources: { cpu: 4, gpu: 1, memory_bytes: 16 * 1024 ** 3 }, duration_seconds: 2.5,
        diagnostic: {
          scoped_node_path: 'preprocessing/segment', category: 'runtime',
          exception_type: 'RuntimeError', message: 'CUDA failed', traceback: 'trace',
          retry_status: 'terminal', terminal: true,
        },
      }],
    })

    const wrapper = mount(ExecutionPanel, {
      global: primeVueTestGlobal({ pinia, dialog: true }),
    })
    await flushPromises()
    // The mount refresh can replace history; restore a live snapshot exactly as a websocket does.
    registry.applySnapshot({
      id: 'run-1', revision: 2, workflow_id: 'workflow', workflow_name: 'Workflow',
      target_id: 'cluster', target_label: 'GPU cluster', target_mode: 'managed_remote', backend: 'managed_remote',
      state: 'failed', created_at: '2026-08-03T10:00:00Z',
      command: 'recompute', retry_of_execution_id: 'run-parent',
      child_execution_ids: [], actions: retryActions,
      jobs: [{
        id: 'job-1', scoped_node_path: 'preprocessing/segment', display_name: 'Segment',
        state: 'failed', executor_label: 'gpu',
        resources: { cpu: 4, gpu: 1, memory_bytes: 16 * 1024 ** 3 },
        diagnostic: {
          scoped_node_path: 'preprocessing/segment', category: 'runtime',
          exception_type: 'RuntimeError', message: 'CUDA failed', traceback: 'trace',
          retry_status: 'terminal', terminal: true,
        },
      }],
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('GPU cluster')
    expect(wrapper.text()).toContain('Segment')
    expect(wrapper.text()).toContain('16 GiB')
    expect(wrapper.get('[data-testid="execution-history-provenance"]').text()).toContain(
      'Recompute of run-parent',
    )
    expect(wrapper.get('[data-testid="execution-cancel"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="execution-retry"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-testid="execution-results"]').attributes('disabled')).toBeDefined()
    await wrapper.get('button.job-row').trigger('click')
    expect(wrapper.get('[data-testid="execution-job-details"]').text()).toContain('CUDA failed')
    expect(wrapper.get('[data-testid="execution-recompute"]').attributes('disabled')).toBeUndefined()

    registry.applySnapshot({
      ...registry.selectedRun!,
      revision: 3,
      state: 'succeeded',
      actions: {
        ...retryActions,
        download_results: { available: true, reason: null },
      },
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.get('[data-testid="execution-results"]').attributes('disabled')).toBeUndefined()
  })

  it('previews and confirms the server-persisted retry plan digest', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const registry = useExecutionRegistryStore()
    const parent = {
      id: 'run-parent', revision: 1, workflow_id: 'workflow', target_id: 'cluster',
      target_label: 'GPU cluster', target_mode: 'managed_remote' as const, backend: 'managed_remote' as const,
      state: 'failed' as const, created_at: '2026-08-03T10:00:00Z',
      retry_of_execution_id: null, child_execution_ids: [], actions: retryActions, jobs: [],
    }
    registry.applySnapshot(parent)
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: {
        plan_digest: 'sha256:confirmed', parent_execution_id: 'run-parent',
        child_execution_id: 'run-child', mode: 'retry',
        target: { id: 'cluster', label: 'GPU cluster', mode: 'managed_remote' },
        recompute: null, invalidations: [], conflicting_run_ids: [], confirmable: true,
      } })
      .mockResolvedValueOnce({ data: {
        revision: 0, execution_id: 'run-child', workflow_id: 'workflow',
        backend: 'managed_remote', target_id: 'cluster', target_label: 'GPU cluster',
        target_mode: 'managed_remote', scheduler_job_id: 'scheduler-child', command: 'retry',
        state: 'prepared', retry_of_execution_id: 'run-parent',
        child_execution_ids: [], actions: {
          cancel: { available: true, reason: null },
          retry: { available: false, reason: 'not terminal' },
          recompute: { available: false, reason: 'not terminal' },
          download_results: { available: false, reason: 'not succeeded' },
        }, jobs: {}, progress_cursor: 0, observation: { reachable: true, error: null },
        created_at: '2026-08-03T10:01:00Z', updated_at: '2026-08-03T10:01:00Z',
      } })
    const wrapper = mount(ExecutionPanel, {
      global: primeVueTestGlobal({ pinia, dialog: true }),
    })
    await flushPromises()
    registry.applySnapshot(parent)
    await wrapper.vm.$nextTick()

    await wrapper.get('[data-testid="execution-retry"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="execution-retry-dialog"]').text()).toContain('run-child')
    await wrapper.get('[data-testid="confirm-execution-retry"]').trigger('click')
    await flushPromises()

    expect(vi.mocked(api.post).mock.calls[1]?.[1]).toEqual({ plan_digest: 'sha256:confirmed' })
    expect(registry.selectedRunId).toBe('run-child')
  })

  it('previews and applies cleanup for the exact managed run identity', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const registry = useExecutionRegistryStore()
    const run = {
      id: 'run-cleanup', revision: 1, workflow_id: 'workflow', target_id: 'profile-cluster',
      target_label: 'GPU cluster', target_mode: 'managed_remote' as const,
      backend: 'managed_remote' as const, state: 'succeeded' as const,
      created_at: '2026-08-03T10:00:00Z', retry_of_execution_id: null,
      child_execution_ids: [], actions: retryActions, jobs: [],
    }
    registry.applySnapshot(run)
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: {
        execution_id: 'run-cleanup', plan_digest: 'sha256:cleanup',
        plan: { run_ids: ['run-cleanup'] },
      } })
      .mockResolvedValueOnce({ data: {
        execution_id: 'run-cleanup', report: { removed: ['run-cleanup'] },
      } })
    const wrapper = mount(ExecutionPanel, {
      global: primeVueTestGlobal({ pinia, dialog: true }),
    })
    await flushPromises()
    registry.applySnapshot(run)
    await wrapper.vm.$nextTick()

    await wrapper.get('[data-testid="execution-cleanup"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="execution-cleanup-dialog"]').text()).toContain(
      'sha256:cleanup',
    )
    await wrapper.get('[data-testid="confirm-execution-cleanup"]').trigger('click')
    await flushPromises()

    expect(vi.mocked(api.post).mock.calls.map(call => call[0])).toEqual([
      '/api/v1/executions/run-cleanup/cleanup/plan',
      '/api/v1/executions/run-cleanup/cleanup',
    ])
    expect(vi.mocked(api.post).mock.calls[0]?.[1]).toEqual({
      older_than_seconds: 0,
    })
    expect(wrapper.text()).toContain('platform history entry is retained')
  })

  it.each([
    'retry-plan-integrity-error',
    'retry-child-conflict',
  ])('requires an explicit new preview for %s', async (errorCode) => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const registry = useExecutionRegistryStore()
    const parent = {
      id: 'run-parent', revision: 1, workflow_id: 'workflow', target_id: 'cluster',
      target_label: 'GPU cluster', target_mode: 'managed_remote' as const, backend: 'managed_remote' as const,
      state: 'failed' as const, created_at: '2026-08-03T10:00:00Z',
      retry_of_execution_id: null, child_execution_ids: [], actions: retryActions,
      jobs: [{
        id: 'segment', scoped_node_path: 'analysis/segment', display_name: 'Segment',
        state: 'failed' as const,
      }],
    }
    const plan = (digest: string) => ({
      plan_digest: digest, parent_execution_id: 'run-parent',
      child_execution_id: 'run-child', mode: 'recompute' as const,
        target: { id: 'cluster', label: 'GPU cluster', mode: 'managed_remote' as const },
      recompute: { node_paths: ['analysis/segment'], cascade: true },
      invalidations: [], conflicting_run_ids: [], confirmable: true,
    })
    registry.applySnapshot(parent)
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: plan('sha256:old') })
      .mockRejectedValueOnce(Object.assign(new Error('Conflict'), {
        response: {
          status: 409,
          data: { error: errorCode, detail: 'Plan is stale' },
        },
      }))
      .mockResolvedValueOnce({ data: plan('sha256:refreshed') })
    const wrapper = mount(ExecutionPanel, {
      global: primeVueTestGlobal({ pinia, dialog: true }),
    })
    await flushPromises()
    registry.applySnapshot(parent)
    await wrapper.vm.$nextTick()

    await wrapper.get('button.job-row').trigger('click')
    await wrapper.get('[data-testid="execution-recompute"]').trigger('click')
    await wrapper.get('[data-testid="preview-execution-retry"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="confirm-execution-retry"]').trigger('click')
    await flushPromises()

    const recompute = { node_paths: ['analysis/segment'], cascade: true }
    expect(vi.mocked(api.post).mock.calls[0]?.[1]).toEqual({ recompute })
    expect(vi.mocked(api.post).mock.calls[1]?.[1]).toEqual({ plan_digest: 'sha256:old' })
    expect(vi.mocked(api.post)).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="retry-plan-error"]').text()).toContain(
      'Select Preview',
    )
    expect(wrapper.find('[data-testid="preview-execution-retry"]').exists()).toBe(true)
    await wrapper.get('[data-testid="preview-execution-retry"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.post).mock.calls[2]?.[1]).toEqual({ recompute })
    expect(wrapper.get('[data-testid="execution-retry-dialog"]').text()).toContain(
      'sha256:refreshed',
    )
    expect(registry.selectedRunId).toBe('run-parent')
  })

  it('observes the exact confirmed child after an uncertain submission', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const registry = useExecutionRegistryStore()
    const parent = {
      id: 'run-parent', revision: 1, workflow_id: 'workflow', target_id: 'cluster',
      target_label: 'GPU cluster', target_mode: 'managed_remote' as const, backend: 'managed_remote' as const,
      state: 'failed' as const, created_at: '2026-08-03T10:00:00Z', command: 'workflow',
      retry_of_execution_id: null, child_execution_ids: [], actions: retryActions, jobs: [],
    }
    registry.applySnapshot(parent)
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: {
        plan_digest: 'sha256:uncertain', parent_execution_id: 'run-parent',
        child_execution_id: 'run-child', mode: 'retry',
        target: { id: 'cluster', label: 'GPU cluster', mode: 'managed_remote' },
        recompute: null, invalidations: [], conflicting_run_ids: [], confirmable: true,
      } })
      .mockRejectedValueOnce(Object.assign(new Error('Submission uncertain'), {
        response: {
          status: 409,
          data: {
            error: 'remote-retry-submission-uncertain',
            detail: 'Scheduler acknowledgement was lost',
            details: { retry_run_id: 'run-child' },
          },
        },
      }))
    const wrapper = mount(ExecutionPanel, {
      global: primeVueTestGlobal({ pinia, dialog: true }),
    })
    await flushPromises()
    registry.applySnapshot(parent)
    await wrapper.vm.$nextTick()
    vi.mocked(api.get).mockResolvedValueOnce({ data: {
      revision: 1, execution_id: 'run-child', workflow_id: 'workflow',
      backend: 'managed_remote', target_id: 'cluster', target_label: 'GPU cluster',
      target_mode: 'managed_remote', scheduler_job_id: 'scheduler-child',
      state: 'starting', command: 'retry', retry_of_execution_id: 'run-parent',
      child_execution_ids: [], actions: {
        cancel: { available: true, reason: null },
        retry: { available: false, reason: 'not terminal' },
        recompute: { available: false, reason: 'not terminal' },
        download_results: { available: false, reason: 'not succeeded' },
      }, jobs: {}, progress_cursor: 0, observation: { reachable: true, error: null },
      created_at: '2026-08-03T10:01:00Z', updated_at: '2026-08-03T10:01:00Z',
    } })

    await wrapper.get('[data-testid="execution-retry"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="confirm-execution-retry"]').trigger('click')
    await flushPromises()

    expect(registry.selectedRunId).toBe('run-child')
    const getCalls = vi.mocked(api.get).mock.calls
    expect(getCalls[getCalls.length - 1]?.[0]).toBe('/api/v1/executions/run-child')
    expect(wrapper.find('[data-testid="execution-retry-dialog"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="execution-history-provenance"]').text()).toContain(
      'Retry of run-parent',
    )
  })

  it('does not replan an unrelated conflict response', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const registry = useExecutionRegistryStore()
    const parent = {
      id: 'run-parent', revision: 1, workflow_id: 'workflow', target_id: 'cluster',
      target_label: 'Cluster', target_mode: 'managed_remote' as const, backend: 'managed_remote' as const,
      state: 'failed' as const,
      created_at: '2026-08-03T10:00:00Z', retry_of_execution_id: null,
      child_execution_ids: [], actions: retryActions, jobs: [],
    }
    registry.applySnapshot(parent)
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: {
        plan_digest: 'sha256:confirmed', parent_execution_id: 'run-parent',
        child_execution_id: 'run-child', mode: 'retry',
        target: { id: 'cluster', label: 'Cluster', mode: 'managed_remote' },
        recompute: null, invalidations: [], conflicting_run_ids: [], confirmable: true,
      } })
      .mockRejectedValueOnce(Object.assign(new Error('Conflict'), {
        response: {
          status: 409,
          data: { error: 'workflow-result-integrity-error', detail: 'Unrelated conflict' },
        },
      }))
    const wrapper = mount(ExecutionPanel, {
      global: primeVueTestGlobal({ pinia, dialog: true }),
    })
    await flushPromises()
    registry.applySnapshot(parent)
    await wrapper.vm.$nextTick()

    await wrapper.get('[data-testid="execution-retry"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="confirm-execution-retry"]').trigger('click')
    await flushPromises()

    expect(vi.mocked(api.post)).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="retry-plan-error"]').text()).toContain('Unrelated conflict')
    expect(wrapper.find('[data-testid="confirm-execution-retry"]').exists()).toBe(true)
  })

  it('uses structured diagnostics instead of retained logs for managed runs', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const registry = useExecutionRegistryStore()
    const submitted = {
      id: 'run-logs', revision: 1, workflow_id: 'workflow', target_id: 'cluster',
      target_label: 'Cluster', target_mode: 'managed_remote' as const, backend: 'managed_remote' as const,
      state: 'running' as const,
      created_at: '2026-08-03T10:00:00Z', retry_of_execution_id: null,
      child_execution_ids: [], actions: retryActions,
      diagnostics: [{
        schema: 'bioimageflow.cluster_diagnostic.v1' as const,
        phase: 'monitor', category: 'connection', message: 'SSH connection was interrupted',
        allocation_state: 'unknown' as const, retry_safety: 'same-attempt-only' as const,
        next_action: 'Check SSH access and refresh this exact run.',
      }],
      jobs: [{
        id: 'job-logs', scoped_node_path: 'analysis/segment', state: 'running' as const,
      }],
    }
    registry.applySnapshot(submitted)
    const wrapper = mount(ExecutionPanel, {
      global: primeVueTestGlobal({ pinia, dialog: true }),
    })
    await flushPromises()
    registry.applySnapshot(submitted)
    await wrapper.vm.$nextTick()
    await wrapper.get('button.job-row').trigger('click')

    expect(wrapper.find('[data-testid="execution-job-logs"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="execution-cluster-diagnostics"]').text()).toContain(
      'Check SSH access and refresh this exact run.',
    )

    const getCallCount = vi.mocked(api.get).mock.calls.length
    registry.applySnapshot({
      ...submitted,
      revision: 2,
      target_id: 'local',
      target_label: 'Local',
      target_mode: 'local',
      backend: 'direct',
      diagnostics: [],
    })
    await wrapper.vm.$nextTick()
    await wrapper.get('[data-testid="execution-job-logs"]').trigger('click')

    expect(useUIStore().panels.logger).toBe(true)
    expect(vi.mocked(api.get)).toHaveBeenCalledTimes(getCallCount)
  })
})
