import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

import { api } from '@/api/client'
import {
  applyPreparedExecution,
  applyExecutionCleanup,
  downloadExecutionResults,
  executionErrorCode,
  executionErrorDetails,
  executionErrorMessage,
  executionResultErrorMessage,
  fetchExecutionTargets,
  fetchExecutions,
  planExecutionRetry,
  planExecutionCleanup,
  preflightExecution,
  startExecutionRetry,
  type ManagedExecutionIntent,
} from '@/api/executions'

const request: ManagedExecutionIntent = {
  workflow_id: 'demo',
  draft_revision: 3,
  target_id: 'profile_1',
  profile_revision: 2,
  command: { kind: 'workflow' },
}

describe('distributed execution API adapter', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
  })

  it('maps the public BioImageFlow path plan into explicit UI choices', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        kind: 'resolution_required',
        unresolved: [{ scoped_node_path: 'files', input_name: 'path' }],
        remote_node_paths: {
          inputs: [{
            scoped_node_path: 'files', input_name: 'path', value_shape: 'path',
            nullable: false, path_picker: 'folder', current_paths: ['images'],
            cluster_compatible: false,
          }],
        },
      },
    })

    const response = await preflightExecution(request)

    expect(response).toEqual({
      status: 'resolution_required',
      unresolved_paths: [{
        node_path: 'files', input_name: 'path', value_shape: 'path',
        values: ['images'], nullable: false, path_picker: 'folder',
        cluster_compatible: false,
      }],
    })
  })

  it('sends scoped invocation-only choices and normalizes retained snapshots', async () => {
    vi.mocked(api.post)
      .mockResolvedValueOnce({
        data: {
          kind: 'ready', token: 'prepared', expires_at: 1_800_000_000,
          resolved_inputs: 2,
        },
      })
      .mockResolvedValueOnce({
        data: {
          revision: 0, execution_id: 'run_1', workflow_id: 'demo',
          draft_revision: 3, backend: 'managed_remote', target_id: 'profile_1',
          target_label: 'GPU queue', target_mode: 'managed_remote',
          scheduler_job_id: 'scheduler-42', command: 'run',
          state: 'prepared', retry_of_execution_id: null, child_execution_ids: [],
          actions: {
            cancel: { available: true, reason: null },
            retry: { available: false, reason: 'not terminal' },
            recompute: { available: false, reason: 'not terminal' },
            download_results: { available: false, reason: 'not succeeded' },
          }, jobs: {}, progress_cursor: 0, observation: { reachable: true, error: null },
          created_at: '2026-08-03T12:00:00Z', updated_at: '2026-08-03T12:00:00Z',
        },
      })
    const choiceRequest: ManagedExecutionIntent = {
      ...request,
      node_path_resolutions: [
        {
          node_path: 'files', input_name: 'path', value_shape: 'path',
          values: [{ source: 'upload', path: '/local/images' }],
        },
        {
          node_path: 'files', input_name: 'mask', value_shape: 'path',
          values: [{ source: 'cluster', path: '/cluster/mask.tif' }],
        },
      ],
    }

    const prepared = await preflightExecution(choiceRequest)
    if (prepared.status !== 'ready') throw new Error('expected ready')
    const snapshot = await applyPreparedExecution(prepared.token, choiceRequest)

    expect(vi.mocked(api.post).mock.calls[0]?.[1]).toMatchObject({
      profile_revision: 2,
      node_path_choices: {
        files: {
          path: { source: 'upload', value: '/local/images' },
          mask: { source: 'cluster', value: '/cluster/mask.tif' },
        },
      },
    })
    expect(vi.mocked(api.post).mock.calls[1]?.[1]).toEqual({
      token: 'prepared', workflow_id: 'demo', draft_revision: 3,
      target_id: 'profile_1', requested_nodes: null,
    })
    expect(snapshot).toMatchObject({
      id: 'run_1', workflow_id: 'demo', target_mode: 'managed_remote',
      target_label: 'GPU queue', scheduler_job_id: 'scheduler-42',
      state: 'prepared', jobs: [],
    })
  })

  it('retains execution capabilities and uses offset pagination', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: {
        capabilities: {
          schema: 'bioimageflow.execution_capabilities.v1',
          capabilities: { submitted_run_retry: { supported: true, reason: null } },
        },
        targets: [{
          id: 'local', name: 'Local', mode: 'local', available: true,
          disabled_reason: null, profile_revision: null,
        }],
      } })
      .mockResolvedValueOnce({ data: { items: [], total: 75, offset: 50, limit: 25 } })

    const targets = await fetchExecutionTargets()
    const page = await fetchExecutions({ workflowId: 'demo', offset: 50, limit: 25 })

    expect(targets.capabilities.capabilities.submitted_run_retry?.supported).toBe(true)
    expect(targets.targets[0]?.label).toBe('Local')
    expect(vi.mocked(api.get).mock.calls[1]?.[1]?.params).toEqual({
      workflow_id: 'demo', offset: 50, limit: 25,
    })
    expect(page).toEqual({ items: [], total: 75, offset: 50, limit: 25 })
  })

  it('plans and starts the exact server-persisted digest and downloads with no request body', async () => {
    const plan = {
      plan_digest: 'sha256:plan', parent_execution_id: 'run-parent',
      child_execution_id: 'run-child', mode: 'recompute' as const,
      target: { id: 'cluster', label: 'Cluster', mode: 'managed_remote' as const },
      recompute: { node_paths: ['analysis/segment'], cascade: true },
      invalidations: [], conflicting_run_ids: [], confirmable: true,
    }
    const child = {
      revision: 0, execution_id: 'run-child', workflow_id: 'demo',
      backend: 'managed_remote', target_id: 'cluster', state: 'prepared',
      target_label: 'GPU queue', target_mode: 'managed_remote',
      scheduler_job_id: 'scheduler-child', command: 'retry',
      retry_of_execution_id: 'run-parent', child_execution_ids: [],
      actions: {
        cancel: { available: true, reason: null },
        retry: { available: false, reason: 'not terminal' },
        recompute: { available: false, reason: 'not terminal' },
        download_results: { available: false, reason: 'not succeeded' },
      },
      jobs: {}, progress_cursor: 0, observation: { reachable: true, error: null },
      created_at: '2026-08-03T12:00:00Z', updated_at: '2026-08-03T12:00:00Z',
    }
    const blob = new Blob(['bundle'])
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: plan })
      .mockResolvedValueOnce({ data: child })
      .mockResolvedValueOnce({ data: blob })

    const preview = await planExecutionRetry('run-parent', plan.recompute)
    const started = await startExecutionRetry('run-parent', preview.plan_digest)
    const downloaded = await downloadExecutionResults('run-child')

    expect(vi.mocked(api.post).mock.calls[0]?.[1]).toEqual({ recompute: plan.recompute })
    expect(vi.mocked(api.post).mock.calls[1]?.[1]).toEqual({ plan_digest: 'sha256:plan' })
    expect(vi.mocked(api.post).mock.calls[2]?.[1]).toBeUndefined()
    expect(started).toMatchObject({
      id: 'run-child', retry_of_execution_id: 'run-parent',
      target_label: 'GPU queue', target_mode: 'managed_remote',
      scheduler_job_id: 'scheduler-child',
    })
    expect(downloaded).toBe(blob)
  })

  it('plans and applies cleanup from the retained run identity', async () => {
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: {
        execution_id: 'run/remote', plan_digest: 'sha256:cleanup',
        plan: { namespace: 'runs', run_ids: ['run/remote'] },
      } })
      .mockResolvedValueOnce({ data: {
        execution_id: 'run/remote', report: { removed: 1 },
      } })

    const plan = await planExecutionCleanup('run/remote')
    await applyExecutionCleanup('run/remote', plan.plan_digest)

    expect(vi.mocked(api.post).mock.calls).toEqual([
      ['/api/v1/executions/run%2Fremote/cleanup/plan', { older_than_seconds: 0 }],
      ['/api/v1/executions/run%2Fremote/cleanup', { plan_digest: 'sha256:cleanup' }],
    ])
  })

  it('decodes structured errors returned through the result download blob channel', async () => {
    const cause = Object.assign(new Error('Request failed'), {
      response: {
        data: new Blob([JSON.stringify({
          detail: {
            error: 'result_unavailable',
            detail: 'The retained result is no longer available.',
            details: { run_id: 'run-child' },
          },
        })], { type: 'application/json' }),
      },
    })

    await expect(executionResultErrorMessage(cause, 'Download failed.')).resolves.toBe(
      'The retained result is no longer available.',
    )
  })

  it('normalizes FastAPI nested structured errors for safe uncertain-run recovery', () => {
    const cause = Object.assign(new Error('Request failed'), {
      response: { data: { detail: {
        error: 'remote-submission-uncertain',
        phase: 'submit',
        message: 'The scheduler acknowledgement was lost.',
        identities: { run_id: 'run-child', attempt_id: 'attempt-1' },
      } } },
    })

    expect(executionErrorCode(cause)).toBe('remote-submission-uncertain')
    expect(executionErrorDetails(cause)).toEqual({
      run_id: 'run-child', attempt_id: 'attempt-1',
    })
    expect(executionErrorMessage(cause, 'fallback')).toBe(
      'The scheduler acknowledgement was lost.',
    )
  })
})
