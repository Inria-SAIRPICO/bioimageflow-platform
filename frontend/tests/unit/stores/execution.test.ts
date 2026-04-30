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

describe('execution store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('starts idle with isRunning false and empty nodeStatuses', () => {
    const store = useExecutionStore()
    expect(store.state).toBe('idle')
    expect(store.isRunning).toBe(false)
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
    mockedApi.post.mockResolvedValueOnce({ data: { status: 'started' } })

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

    await store.run(graph)

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/execution/run', {
      graph,
      nodes: undefined,
      workflow_name: null,
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

  it('run with nodes passes node list', async () => {
    const graph = { nodes: [], edges: [] }
    const nodes = ['n1', 'n2']
    mockedApi.post.mockResolvedValueOnce({ data: {} })

    const store = useExecutionStore()
    await store.run(graph, nodes)

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/execution/run', {
      graph,
      nodes,
      workflow_name: null,
    })
  })

  it('run sets isConflict when server returns 409', async () => {
    const graph = { nodes: [], edges: [] }
    mockedApi.post.mockRejectedValueOnce({ response: { status: 409 } })

    const store = useExecutionStore()
    await expect(store.run(graph)).rejects.toBeTruthy()
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
    await expect(store.run(graph)).rejects.toBeTruthy()
    expect(store.validationErrors).toHaveLength(1)
    expect(store.validationErrors[0].type).toBe('cycle_detected')
  })

  it('stop sends POST /execution/stop and waits for backend log messages', async () => {
    mockedApi.post.mockResolvedValueOnce({ data: {} })

    const store = useExecutionStore()
    const logger = useLoggerStore()
    logger.addEntry({
      level: 'INFO',
      message: 'pre-existing',
      nodeId: null,
      timestamp: 1,
    })
    store.state = 'running'
    await store.stop()

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/execution/stop')
    // Per F1: stop waits for server, does not immediately change state.
    expect(store.state).toBe('running')
    expect(logger.entries).toEqual([
      expect.objectContaining({
        level: 'INFO',
        message: 'pre-existing',
        nodeId: null,
      }),
    ])
  })

  it('clear sends {graph, nodes} and merges returned node_statuses', async () => {
    const graph = { nodes: [], edges: [] }
    const responseData = {
      node_statuses: {
        n1: { node_id: 'n1', status: 'unexecuted', cached: false },
        n2: { node_id: 'n2', status: 'out_of_date', cached: false },
      },
    }
    mockedApi.post.mockResolvedValueOnce({ data: responseData })

    const store = useExecutionStore()
    const result = await store.clear(graph, ['n1', 'n2'])

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/execution/clear', {
      graph,
      nodes: ['n1', 'n2'],
      workflow_name: null,
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

  it('applyProgress updates progress', () => {
    const store = useExecutionStore()
    const p: ProgressInfo = { node_id: 'n1', row: 5, total_rows: 10 }
    store.applyProgress(p)
    expect(store.progress).toEqual(p)
  })

  it('applyNodeState writes into nodeStatuses by node_id', () => {
    const store = useExecutionStore()
    store.applyNodeState({
      node_id: 'n1',
      status: 'running',
      cached: false,
    })
    expect(store.nodeStatuses.n1).toEqual({
      node_id: 'n1',
      status: 'running',
      cached: false,
      error: null,
      traceback: null,
    })
  })

  it('applyExecutionComplete sets idle, merges node_statuses, clears progress', () => {
    const store = useExecutionStore()
    store.state = 'running'
    store.progress = { node_id: 'n1', row: 3, total_rows: 10 }

    const result: ExecutionResult = {
      success: true,
      errors: [],
      node_statuses: {
        n1: { node_id: 'n1', status: 'executed', cached: false },
      },
    }
    store.applyExecutionComplete(result)

    expect(store.state).toBe('idle')
    expect(store.lastResult).toEqual(result)
    expect(store.progress).toBeNull()
    expect(store.nodeStatuses.n1.status).toBe('executed')
  })

  it('run rejects when already running', async () => {
    const store = useExecutionStore()
    store.state = 'running'

    await expect(store.run({ nodes: [], edges: [] })).rejects.toThrow(
      'already running',
    )
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
    await expect(store.run({ nodes: [], edges: [] })).rejects.toThrow(
      'Server error',
    )
    expect(store.state).toBe('idle')
    expect(store.error).toBe('Server error')
  })

  describe('execution_failed reporting', () => {
    it('does NOT report on success=true', async () => {
      const errorsModule = await import('@/stores/errors')
      const errorStore = errorsModule.useErrorStore()
      const store = useExecutionStore()

      store.applyExecutionComplete({
        success: true,
        errors: [],
        node_statuses: {
          n1: { node_id: 'n1', status: 'executed', cached: false },
        },
      })
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

      store.applyExecutionComplete({
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
      })
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

      store.applyExecutionComplete({
        success: false,
        errors: [
          {
            type: 'RuntimeError',
            detail: 'pre-execution validation failed',
            traceback: 'Traceback line 1\nTraceback line 2',
          },
        ],
        node_statuses: {},
      })
      expect(errorStore.errors).toHaveLength(1)
      expect(errorStore.errors[0]!.kind).toBe('execution_failed')
      expect(errorStore.errors[0]!.detail).toContain(
        'pre-execution validation failed',
      )
      expect(errorStore.errors[0]!.fullDetail).toContain('Traceback line 2')
      expect(useLoggerStore().entries).toEqual([])
    })

    it('emits one report even when multiple nodes failed', async () => {
      const errorsModule = await import('@/stores/errors')
      const errorStore = errorsModule.useErrorStore()
      const store = useExecutionStore()

      store.applyExecutionComplete({
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
      })
      expect(errorStore.errors).toHaveLength(1)
      // Detail should mention that more than one node failed.
      expect(errorStore.errors[0]!.detail).toContain('failed')
    })
  })
})
