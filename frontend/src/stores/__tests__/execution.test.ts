import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

import { useExecutionStore } from '../execution'
import { useLoggerStore } from '../logger'
import { useErrorStore } from '../errors'
import { api } from '@/api/client'

describe('execution store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.post).mockReset()
  })

  it('preserves execution failure details without duplicating backend logger entries', () => {
    const execution = useExecutionStore()
    const logger = useLoggerStore()
    const errors = useErrorStore()
    logger.addEntry({
      level: 'ERROR',
      nodeId: 'node_a',
      message: 'Node node_a failed: segmentation failed\nTraceback...\nValueError: bad image',
      timestamp: 1,
    })

    execution.state = 'running'
    execution.applyExecutionComplete({
      success: false,
      errors: [{ type: 'RuntimeError', detail: 'top-level failure' }],
      node_statuses: {
        node_a: {
          node_id: 'node_a',
          status: 'failed',
          cached: false,
          error: 'segmentation failed',
          traceback: 'Traceback...\nValueError: bad image',
        },
      },
    })

    expect(logger.entries).toHaveLength(1)
    expect(logger.entries[0]!.message).toContain('ValueError: bad image')
    expect(errors.errors[0]).toMatchObject({
      kind: 'execution_failed',
      detail: 'node_a: segmentation failed',
      nodeId: 'node_a',
      fullDetail: expect.stringContaining('ValueError: bad image'),
    })
  })

  it('captures environment delete recovery actions from execution failures', () => {
    const execution = useExecutionStore()

    execution.state = 'running'
    execution.applyExecutionComplete({
      success: false,
      errors: [{
        type: 'EnvironmentReuseError',
        detail: 'Environment recipe mismatch',
        recovery_action: {
          kind: 'delete_environment',
          env_name: 'cellpose-env',
          path: '/wetlands/pixi/workspaces/cellpose-env/pixi.toml',
          existing_hash: 'sha256:old',
          requested_hash: 'sha256:new',
        },
      }],
      node_statuses: {
        cellpose_1: {
          node_id: 'cellpose_1',
          status: 'failed',
          cached: false,
          error: 'Environment recipe mismatch',
        },
      },
    })

    expect(execution.environmentRecoveryAction).toEqual({
      kind: 'delete_environment',
      envName: 'cellpose-env',
      path: '/wetlands/pixi/workspaces/cellpose-env/pixi.toml',
      existingHash: 'sha256:old',
      requestedHash: 'sha256:new',
      nodeId: 'cellpose_1',
    })
    expect(execution.isEnvironmentRecoveryDialogVisible).toBe(true)
  })

  it('dismisses and clears environment recovery actions when a new run starts', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { status: 'started' } })
    const execution = useExecutionStore()
    execution.state = 'running'
    execution.applyExecutionComplete({
      success: false,
      errors: [{
        detail: 'Environment recipe mismatch',
        recovery_action: {
          kind: 'delete_environment',
          env_name: 'cellpose-env',
        },
      }],
      node_statuses: {},
    })

    execution.dismissEnvironmentRecovery()
    expect(execution.isEnvironmentRecoveryDialogVisible).toBe(false)

    await execution.run({ nodes: [], edges: [] }, undefined, 'wf_a')

    expect(execution.environmentRecoveryAction).toBeNull()
    expect(execution.isEnvironmentRecoveryDialogVisible).toBe(false)
  })

  it('posts workflow_name when starting execution', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { status: 'started' } })
    const execution = useExecutionStore()
    const graph = { nodes: [], edges: [] }

    await execution.run(graph, undefined, 'wf_a')

    expect(api.post).toHaveBeenCalledWith('/api/v1/execution/run', {
      graph,
      nodes: undefined,
      workflow_name: 'wf_a',
    })
  })

  it('posts workflow_name when clearing cache', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { node_statuses: {} } })
    const execution = useExecutionStore()
    const graph = { nodes: [], edges: [] }

    await execution.clear(graph, ['n1'], 'wf_a')

    expect(api.post).toHaveBeenCalledWith('/api/v1/execution/clear', {
      graph,
      nodes: ['n1'],
      workflow_name: 'wf_a',
    })
  })
})
