import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

import { api } from '@/api/client'
import { useExecutionStore } from '@/stores/execution'
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

  it('starts idle with isRunning false and null lastResult/progress', () => {
    const store = useExecutionStore()
    expect(store.state).toBe('idle')
    expect(store.isRunning).toBe(false)
    expect(store.lastResult).toBeNull()
    expect(store.progress).toBeNull()
    expect(store.error).toBeNull()
  })

  it('fetchStatus populates from GET /api/v1/execution/status', async () => {
    const result: ExecutionResult = {
      success: true,
      errors: [],
      node_statuses: {
        n1: { node_id: 'n1', status: 'executed', cached: false },
      },
    }
    mockedApi.get.mockResolvedValueOnce({
      data: { state: 'running', last_result: result, progress: null },
    })

    const store = useExecutionStore()
    await store.fetchStatus()

    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/execution/status')
    expect(store.state).toBe('running')
    expect(store.lastResult).toEqual(result)
    expect(store.progress).toBeNull()
  })

  it('run sends POST and sets running, clears lastResult and progress', async () => {
    const graph = { nodes: [], edges: [] }
    mockedApi.post.mockResolvedValueOnce({ data: {} })

    const store = useExecutionStore()
    // Pre-populate to verify they get cleared
    store.lastResult = {
      success: true,
      errors: [],
      node_statuses: {
        n1: { node_id: 'n1', status: 'executed', cached: false },
      },
    }
    store.progress = { node_id: 'n1', row: 5, total_rows: 10 }

    await store.run(graph)

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/execution/run', {
      graph,
      nodes: undefined,
    })
    expect(store.state).toBe('running')
    expect(store.lastResult).toBeNull()
    expect(store.progress).toBeNull()
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
    })
  })

  it('stop sends POST /execution/stop', async () => {
    mockedApi.post.mockResolvedValueOnce({ data: {} })

    const store = useExecutionStore()
    store.state = 'running'
    await store.stop()

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/execution/stop')
    expect(store.state).toBe('idle')
  })

  it('clear sends POST /execution/clear with nodes and returns data', async () => {
    const responseData = { cleared: ['n1', 'n2'] }
    mockedApi.post.mockResolvedValueOnce({ data: responseData })

    const store = useExecutionStore()
    const result = await store.clear(['n1', 'n2'])

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/execution/clear', {
      nodes: ['n1', 'n2'],
    })
    expect(result).toEqual(responseData)
  })

  it('applyProgress updates progress', () => {
    const store = useExecutionStore()
    const p: ProgressInfo = { node_id: 'n1', row: 5, total_rows: 10 }
    store.applyProgress(p)
    expect(store.progress).toEqual(p)
  })

  it('applyExecutionComplete sets idle, populates lastResult, clears progress', () => {
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

  it('run handles API errors gracefully', async () => {
    mockedApi.post.mockRejectedValueOnce(new Error('Server error'))

    const store = useExecutionStore()
    await expect(store.run({ nodes: [], edges: [] })).rejects.toThrow(
      'Server error',
    )
    expect(store.state).toBe('idle')
    expect(store.error).toBe('Server error')
  })
})
