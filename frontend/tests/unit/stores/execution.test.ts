import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

import { api } from '@/api/client'
import { useExecutionStore } from '@/stores/execution'
import { useLoggerStore } from '@/stores/logger'
import type { ExecutionResult, ProgressInfo } from '@/api/types'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function executionContext(
  executionId = 'exec-1',
  workflowId = 'wf_a',
  draftRevision: number | null = null,
) {
  return {
    execution_id: executionId,
    workflow_id: workflowId,
    draft_revision: draftRevision,
  }
}

function contextual<T extends object>(
  payload: T,
  executionId = 'exec-1',
  workflowId = 'wf_a',
  draftRevision: number | null = null,
) {
  return {
    ...payload,
    ...executionContext(executionId, workflowId, draftRevision),
  }
}

describe('execution store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('starts idle with isRunning false and empty nodeStatuses', () => {
    const store = useExecutionStore()
    expect(store.state).toBe('idle')
    expect(store.isRunning).toBe(false)
    expect(store.isMutationLocked).toBe(false)
    expect(store.lastResult).toBeNull()
    expect(store.progress).toBeNull()
    expect(store.error).toBeNull()
    expect(store.nodeStatuses).toEqual({})
    expect(store.isConflict).toBe(false)
    expect(store.validationErrors).toEqual([])
  })

  it('fetchStatus populates state/last_result/progress and merges node_statuses', async () => {
    const result: ExecutionResult = {
      success: true,
      errors: [],
      node_statuses: {
        n1: { node_id: 'n1', status: 'executed', cached: false },
      },
    }
    mockedApi.get.mockResolvedValueOnce({
      data: {
        ...executionContext(),
        state: 'running',
        last_result: result,
        progress: null,
        node_statuses: {
          n2: { node_id: 'n2', status: 'running', cached: false },
        },
      },
    })

    const store = useExecutionStore()
    await store.fetchStatus()

    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/execution/status')
    expect(store.state).toBe('running')
    expect(store.lastResult).toEqual(result)
    expect(store.progress).toBeNull()
    expect(store.nodeStatuses.n2.status).toBe('running')
  })

  it('run sends POST, resets nodeStatuses, preserves logs, and waits for backend logs', async () => {
    const graph = { nodes: [], edges: [] }
    mockedApi.post.mockResolvedValueOnce({
      data: contextual({ status: 'started' }),
    })

    const store = useExecutionStore()
    store.nodeStatuses = {
      n1: { node_id: 'n1', status: 'executed', cached: false },
    }
    store.lastResult = {
      success: true,
      errors: [],
      node_statuses: { n1: { node_id: 'n1', status: 'executed', cached: false } },
    }
    store.progress = { node_id: 'n1', row: 5, total_rows: 10 }
    const logger = useLoggerStore()
    logger.addEntry({
      level: 'INFO',
      message: 'old run',
      nodeId: null,
      timestamp: 1,
    })

    await store.run(graph, undefined, 'wf_a')

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/execution/run', {
      graph,
      nodes: undefined,
      workflow_name: 'wf_a',
    })
    expect(store.state).toBe('running')
    expect(store.lastResult).toBeNull()
    expect(store.progress).toBeNull()
    expect(store.nodeStatuses).toEqual({})
    expect(logger.entries).toEqual([
      expect.objectContaining({
        level: 'INFO',
        message: 'old run',
        nodeId: null,
      }),
    ])
  })

  it('locks synchronously while starting and suppresses duplicate starts', async () => {
    const request = deferred<{ data: { status: string } }>()
    mockedApi.post.mockReturnValueOnce(request.promise)
    const store = useExecutionStore()
    const graph = { nodes: [], edges: [] }

    const start = store.run(graph, undefined, 'wf_a')

    expect(store.state).toBe('starting')
    expect(store.isRunning).toBe(false)
    expect(store.isMutationLocked).toBe(true)
    await expect(store.run(graph, undefined, 'wf_a')).rejects.toThrow(/already/i)
    expect(mockedApi.post).toHaveBeenCalledOnce()

    request.resolve({ data: contextual({ status: 'started' }) })
    await start
    expect(store.state).toBe('running')
    expect(store.isRunning).toBe(true)
  })

  it.each(['starting', 'running', 'stopping'] as const)(
    'rejects a start while execution is %s',
    async (phase) => {
      const store = useExecutionStore()
      store.state = phase as any

      await expect(
        store.run({ nodes: [], edges: [] }, undefined, 'wf_a'),
      ).rejects.toThrow(/already/i)
      expect(mockedApi.post).not.toHaveBeenCalled()
    },
  )

  it('does not let a late start response override a terminal event or newer start', async () => {
    const firstRequest = deferred<{ data: { status: string } }>()
    const secondRequest = deferred<{ data: { status: string } }>()
    mockedApi.post
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)
    const store = useExecutionStore()

    const firstStart = store.run({ nodes: [], edges: [] }, undefined, 'wf_a')
    store.applyExecutionComplete(contextual({
      success: true,
      errors: [],
      node_statuses: {},
    }))
    const secondStart = store.run({ nodes: [], edges: [] }, undefined, 'wf_a')
    expect(store.state).toBe('starting')

    firstRequest.resolve({ data: contextual({ status: 'started' }) })
    await firstStart
    expect(store.state).toBe('starting')

    secondRequest.resolve({ data: contextual({ status: 'started' }, 'exec-2') })
    await secondStart
    expect(store.state).toBe('running')
  })

  it('rolls back a failed start only while that start still owns the phase', async () => {
    const firstRequest = deferred<never>()
    mockedApi.post.mockReturnValueOnce(firstRequest.promise)
    const store = useExecutionStore()

    const start = store.run({ nodes: [], edges: [] }, undefined, 'wf_a')
    expect(store.state).toBe('starting')
    firstRequest.reject(new Error('start failed'))
    await expect(start).rejects.toThrow('start failed')
    expect(store.state).toBe('idle')

    const lateFailure = deferred<never>()
    mockedApi.post.mockReturnValueOnce(lateFailure.promise)
    const nextStart = store.run({ nodes: [], edges: [] }, undefined, 'wf_a')
    store.applyExecutionComplete(contextual({
      success: true,
      errors: [],
      node_statuses: {},
    }))
    lateFailure.reject(new Error('late failure'))
    await expect(nextStart).rejects.toThrow('late failure')
    expect(store.state).toBe('idle')
  })

  it('does not let a stale start failure overwrite a newer start', async () => {
    const firstRequest = deferred<never>()
    const secondRequest = deferred<{ data: { status: string } }>()
    mockedApi.post
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)
    const store = useExecutionStore()

    const firstStart = store.run({ nodes: [], edges: [] }, undefined, 'wf_a')
    store.applyExecutionComplete(contextual({
      success: true,
      errors: [],
      node_statuses: {},
    }))
    const secondStart = store.run({ nodes: [], edges: [] }, undefined, 'wf_a')
    const staleValidationError = {
      type: 'cycle_detected',
      detail: 'stale cycle',
      node: null,
      edge_id: null,
      field: null,
    }

    firstRequest.reject({
      message: 'stale start failed',
      response: {
        status: 422,
        data: { detail: 'stale start failed', errors: [staleValidationError] },
      },
    })
    await expect(firstStart).rejects.toMatchObject({ message: 'stale start failed' })

    expect(store.state).toBe('starting')
    expect(store.error).toBeNull()
    expect(store.isConflict).toBe(false)
    expect(store.validationErrors).toEqual([])
    expect(useLoggerStore().entries).toEqual([])

    secondRequest.resolve({ data: contextual({ status: 'started' }, 'exec-2') })
    await secondStart
    expect(store.state).toBe('running')
  })

  it('rejects entire idle status payloads while a start request is in flight', async () => {
    const request = deferred<{ data: { status: string } }>()
    mockedApi.post.mockReturnValueOnce(request.promise)
    const priorResult: ExecutionResult = {
      success: true,
      errors: [],
      node_statuses: {},
    }
    const staleProgress: ProgressInfo = {
      node_id: 'stale',
      row: 3,
      total_rows: 10,
    }
    mockedApi.get.mockResolvedValueOnce({
      data: {
        state: 'idle',
        last_result: priorResult,
        progress: staleProgress,
        node_statuses: {
          fetched: { node_id: 'fetched', status: 'executed', cached: true },
        },
      },
    })
    const store = useExecutionStore()

    const start = store.run({ nodes: [], edges: [] }, undefined, 'wf_a')
    store.applyStatusSnapshot({
      state: 'idle',
      last_result: priorResult,
      progress: staleProgress,
      node_statuses: {
        snapshot: { node_id: 'snapshot', status: 'executed', cached: true },
      },
    })
    expect(store.state).toBe('starting')
    expect(store.lastResult).toBeNull()
    expect(store.progress).toBeNull()
    expect(store.nodeStatuses).toEqual({})
    await store.fetchStatus()
    expect(store.state).toBe('starting')
    expect(store.lastResult).toBeNull()
    expect(store.progress).toBeNull()
    expect(store.nodeStatuses).toEqual({})

    request.resolve({ data: contextual({ status: 'started' }) })
    await start
    expect(store.state).toBe('running')
  })

  it('run rejects a missing workflow identity before changing execution state', async () => {
    const graph = { nodes: [], edges: [] }
    const store = useExecutionStore()
    const priorStatus = {
      node_id: 'n1',
      status: 'executed' as const,
      cached: true,
    }
    store.nodeStatuses = { n1: priorStatus }

    await expect(store.run(graph, undefined, '')).rejects.toThrow(/workflow/i)

    expect(mockedApi.post).not.toHaveBeenCalled()
    expect(store.state).toBe('idle')
    expect(store.nodeStatuses).toEqual({ n1: priorStatus })
  })

  it('run with nodes passes node list', async () => {
    const graph = { nodes: [], edges: [] }
    const nodes = ['n1', 'n2']
    mockedApi.post.mockResolvedValueOnce({
      data: contextual({ status: 'started' }),
    })

    const store = useExecutionStore()
    await store.run(graph, nodes, 'wf_a')

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/execution/run', {
      graph,
      nodes,
      workflow_name: 'wf_a',
    })
  })

  it('run sets isConflict when server returns 409', async () => {
    const graph = { nodes: [], edges: [] }
    mockedApi.post.mockRejectedValueOnce({ response: { status: 409 } })

    const store = useExecutionStore()
    await expect(store.run(graph, undefined, 'wf_a')).rejects.toBeTruthy()
    expect(store.isConflict).toBe(true)
    expect(store.state).toBe('idle')
  })

  it('run populates validationErrors on 422', async () => {
    const graph = { nodes: [], edges: [] }
    mockedApi.post.mockRejectedValueOnce({
      response: {
        status: 422,
        data: {
          errors: [
            { type: 'cycle_detected', detail: 'cycle', node: null, edge_id: null, field: null },
          ],
        },
      },
    })

    const store = useExecutionStore()
    await expect(store.run(graph, undefined, 'wf_a')).rejects.toBeTruthy()
    expect(store.validationErrors).toHaveLength(1)
    expect(store.validationErrors[0].type).toBe('cycle_detected')
  })

  it('stop locks synchronously, suppresses duplicates, and waits for terminal state', async () => {
    const request = deferred<{ data: Record<string, never> }>()
    mockedApi.post.mockReturnValueOnce(request.promise)

    const store = useExecutionStore()
    const logger = useLoggerStore()
    logger.addEntry({
      level: 'INFO',
      message: 'pre-existing',
      nodeId: null,
      timestamp: 1,
    })
    store.state = 'running'
    const stop = store.stop()

    expect(store.state).toBe('stopping')
    expect(store.isRunning).toBe(true)
    expect(store.isMutationLocked).toBe(true)
    await expect(store.stop()).resolves.toBe(false)
    expect(mockedApi.post).toHaveBeenCalledOnce()
    request.resolve({ data: {} })
    await expect(stop).resolves.toBe(true)
    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/execution/stop')
    expect(store.state).toBe('stopping')
    expect(logger.entries).toEqual([
      expect.objectContaining({
        level: 'INFO',
        message: 'pre-existing',
        nodeId: null,
      }),
    ])
  })

  it('rolls back a failed stop only while that stop still owns the phase', async () => {
    const request = deferred<never>()
    mockedApi.post.mockReturnValueOnce(request.promise)
    const store = useExecutionStore()
    store.applyStatusSnapshot(contextual({
      state: 'running',
      last_result: null,
      progress: null,
    }))

    const stop = store.stop()
    request.reject(new Error('stop failed'))
    await expect(stop).rejects.toThrow('stop failed')
    expect(store.state).toBe('running')

    const lateFailure = deferred<never>()
    mockedApi.post.mockReturnValueOnce(lateFailure.promise)
    const nextStop = store.stop()
    store.applyExecutionComplete(contextual({
      success: true,
      errors: [],
      node_statuses: {},
    }))
    lateFailure.reject(new Error('late stop failure'))
    await expect(nextStop).rejects.toThrow('late stop failure')
    expect(store.state).toBe('idle')
  })

  it('keeps stopping through late running events and unlocks on idle', () => {
    const store = useExecutionStore()
    const progress: ProgressInfo = { node_id: 'n1', row: 1, total_rows: 2 }
    store.applyStatusSnapshot(contextual({
      state: 'running',
      last_result: null,
      progress: null,
    }))
    store.state = 'stopping' as any

    store.applyProgress(contextual(progress))
    store.applyNodeState(contextual({
      node_id: 'n1',
      status: 'running',
      cached: false,
    }))
    store.applyStatusSnapshot(contextual({ state: 'running', last_result: null, progress }))
    expect(store.state).toBe('stopping')
    expect(store.isMutationLocked).toBe(true)

    store.applyStatusSnapshot(contextual({ state: 'idle', last_result: null, progress: null }))
    expect(store.state).toBe('idle')
    expect(store.isMutationLocked).toBe(false)
  })

  it('does not resurrect a terminal execution from late running events', () => {
    const store = useExecutionStore()
    store.applyStatusSnapshot(contextual({
      state: 'running',
      last_result: null,
      progress: null,
    }))
    store.state = 'stopping'
    const result = contextual({ success: true, errors: [], node_statuses: {} })
    store.applyExecutionComplete(result)
    const progress: ProgressInfo = { node_id: 'n1', row: 1, total_rows: 2 }

    store.applyProgress(contextual(progress))
    store.applyNodeState(contextual({
      node_id: 'n1',
      status: 'running',
      cached: false,
    }))
    store.applyStatusSnapshot(contextual({ state: 'running', last_result: null, progress }))

    expect(store.state).toBe('idle')
    expect(store.isMutationLocked).toBe(false)
    expect(store.lastResult).toEqual(result)
  })

  it('clear sends {graph, nodes, workflow_name} and merges returned node_statuses', async () => {
    const graph = { nodes: [], edges: [] }
    const responseData = {
      node_statuses: {
        n1: { node_id: 'n1', status: 'unexecuted', cached: false },
        n2: { node_id: 'n2', status: 'out_of_date', cached: false },
      },
    }
    mockedApi.post.mockResolvedValueOnce({ data: responseData })

    const store = useExecutionStore()
    const result = await store.clear(graph, ['n1', 'n2'], 'workflow-a')

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/execution/clear', {
      graph,
      nodes: ['n1', 'n2'],
      workflow_name: 'workflow-a',
    })
    expect(result).toEqual(responseData)
    expect(store.nodeStatuses.n1.status).toBe('unexecuted')
    expect(store.nodeStatuses.n2.status).toBe('out_of_date')
    expect(useLoggerStore().entries).toEqual([
      expect.objectContaining({
        level: 'INFO',
        message: 'Execution cache cleared for 2 nodes',
        nodeId: null,
      }),
    ])
  })

  it('clear rejects a missing workflow identity before making a request', async () => {
    const store = useExecutionStore()

    await expect(store.clear({ nodes: [], edges: [] }, ['n1'], '')).rejects.toThrow(
      /workflow/i,
    )

    expect(mockedApi.post).not.toHaveBeenCalled()
    expect(store.nodeStatuses).toEqual({})
  })

  it('applyProgress updates progress', () => {
    const store = useExecutionStore()
    const p: ProgressInfo = {
      node_id: 'n1',
      row: 5,
      total_rows: 10,
      result_key: 'rk-n1',
      record_id: 'rec-n1',
    }
    store.applyProgress(contextual(p))
    expect(store.progress).toEqual(contextual(p))
    expect(store.state).toBe('running')
  })

  it('applyNodeState writes into nodeStatuses by node_id', () => {
    const store = useExecutionStore()
    store.applyNodeState(contextual({
      node_id: 'n1',
      status: 'running',
      cached: false,
      result_key: 'rk-n1',
      record_id: 'rec-n1',
    }))
    expect(store.nodeStatuses.n1).toEqual({
      node_id: 'n1',
      status: 'running',
      cached: false,
      error: null,
      traceback: null,
      result_key: 'rk-n1',
      record_id: 'rec-n1',
    })
    expect(store.state).toBe('running')
  })

  it('applyStatusSnapshot reconciles websocket execution state', () => {
    const store = useExecutionStore()
    store.nodeStatuses = {
      old: { node_id: 'old', status: 'executed', cached: false },
    }

    const lastResult: ExecutionResult = {
      success: true,
      errors: [],
      node_statuses: {
        n1: { node_id: 'n1', status: 'executed', cached: false },
      },
    }
    store.applyStatusSnapshot({
      state: 'idle',
      last_result: lastResult,
      progress: null,
      node_statuses: {
        n1: { node_id: 'n1', status: 'executed', cached: false },
      },
    })

    expect(store.state).toBe('idle')
    expect(store.lastResult).toEqual(lastResult)
    expect(store.progress).toBeNull()
    expect(store.nodeStatuses).toEqual({
      n1: { node_id: 'n1', status: 'executed', cached: false },
    })
  })

  it('applyStatusSnapshot replaces stale node statuses from older runs', () => {
    const store = useExecutionStore()
    store.nodeStatuses = {
      a: { node_id: 'a', status: 'executed', cached: false },
      b: { node_id: 'b', status: 'failed', cached: false, error: 'old' },
    }

    store.applyStatusSnapshot(contextual({
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: {
        a: { node_id: 'a', status: 'running', cached: false },
      },
    }))

    expect(store.nodeStatuses).toEqual({
      a: { node_id: 'a', status: 'running', cached: false },
    })
  })

  it('applyExecutionComplete sets idle, merges node_statuses, clears progress', () => {
    const store = useExecutionStore()
    store.applyStatusSnapshot(contextual({
      state: 'running',
      last_result: null,
      progress: { node_id: 'n1', row: 3, total_rows: 10 },
    }))

    const result = contextual({
      success: true,
      errors: [],
      node_statuses: {
        n1: { node_id: 'n1', status: 'executed', cached: false },
      },
    })
    store.applyExecutionComplete(result)

    expect(store.state).toBe('idle')
    expect(store.lastResult).toEqual(result)
    expect(store.progress).toBeNull()
    expect(store.nodeStatuses.n1.status).toBe('executed')
  })

  it('run rejects when already running', async () => {
    const store = useExecutionStore()
    store.state = 'running'

    await expect(
      store.run({ nodes: [], edges: [] }, undefined, 'wf_a'),
    ).rejects.toThrow('already running')
    expect(mockedApi.post).not.toHaveBeenCalled()
  })

  it('fetchStatus handles API errors gracefully', async () => {
    mockedApi.get.mockRejectedValueOnce(new Error('Network error'))

    const store = useExecutionStore()
    await store.fetchStatus()

    expect(store.error).toBe('Network error')
  })

  it('run handles generic API errors gracefully', async () => {
    mockedApi.post.mockRejectedValueOnce(new Error('Server error'))

    const store = useExecutionStore()
    await expect(
      store.run({ nodes: [], edges: [] }, undefined, 'wf_a'),
    ).rejects.toThrow('Server error')
    expect(store.state).toBe('idle')
    expect(store.error).toBe('Server error')
  })

  describe('execution_failed reporting', () => {
    it('does NOT report on success=true', async () => {
      const errorsModule = await import('@/stores/errors')
      const errorStore = errorsModule.useErrorStore()
      const store = useExecutionStore()

      store.applyExecutionComplete(contextual({
        success: true,
        errors: [],
        node_statuses: {
          n1: { node_id: 'n1', status: 'executed', cached: false },
        },
      }))
      expect(errorStore.errors).toHaveLength(0)
    })

    it('reports execution_failed with first failed node id and error', async () => {
      const errorsModule = await import('@/stores/errors')
      const errorStore = errorsModule.useErrorStore()
      const store = useExecutionStore()
      const logger = useLoggerStore()
      logger.addEntry({
        level: 'ERROR',
        message: 'Node b failed: b broke\ntb',
        nodeId: 'b',
        timestamp: 1,
      })

      store.applyExecutionComplete(contextual({
        success: false,
        errors: [],
        node_statuses: {
          a: { node_id: 'a', status: 'executed', cached: false },
          b: {
            node_id: 'b',
            status: 'failed',
            cached: false,
            error: 'b broke',
            traceback: 'tb',
          },
        },
      }))
      expect(errorStore.errors).toHaveLength(1)
      const entry = errorStore.errors[0]!
      expect(entry.kind).toBe('execution_failed')
      expect(entry.nodeId).toBe('b')
      expect(entry.detail).toContain('b broke')
      expect(entry.fullDetail).toContain('tb')
      expect(logger.entries).toHaveLength(1)
      expect(logger.entries[0]!.message).toBe('Node b failed: b broke\ntb')
    })

    it('preserves top-level workflow tracebacks in Error History when no failed node is present', async () => {
      const errorsModule = await import('@/stores/errors')
      const errorStore = errorsModule.useErrorStore()
      const store = useExecutionStore()

      store.applyExecutionComplete(contextual({
        success: false,
        errors: [
          {
            type: 'RuntimeError',
            detail: 'pre-execution validation failed',
            traceback: 'Traceback line 1\nTraceback line 2',
          },
        ],
        node_statuses: {},
      }))
      expect(errorStore.errors).toHaveLength(1)
      expect(errorStore.errors[0]!.kind).toBe('execution_failed')
      expect(errorStore.errors[0]!.detail).toContain(
        'pre-execution validation failed',
      )
      expect(errorStore.errors[0]!.fullDetail).toContain('Traceback line 2')
      expect(useLoggerStore().entries).toEqual([
        expect.objectContaining({
          level: 'ERROR',
          message: expect.stringContaining('Traceback line 2'),
          nodeId: null,
        }),
      ])
    })

    it('emits one report even when multiple nodes failed', async () => {
      const errorsModule = await import('@/stores/errors')
      const errorStore = errorsModule.useErrorStore()
      const store = useExecutionStore()

      store.applyExecutionComplete(contextual({
        success: false,
        errors: [],
        node_statuses: {
          a: {
            node_id: 'a',
            status: 'failed',
            cached: false,
            error: 'a broke',
          },
          b: {
            node_id: 'b',
            status: 'failed',
            cached: false,
            error: 'b broke',
          },
        },
      }))
      expect(errorStore.errors).toHaveLength(1)
      // Detail should mention that more than one node failed.
      expect(errorStore.errors[0]!.detail).toContain('failed')
    })
  })
})
