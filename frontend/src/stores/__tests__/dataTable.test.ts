import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '@/api/client'
import type { NodeDataResponse } from '@/api/types'
import { useDataTableStore } from '@/stores/dataTable'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn() },
}))

const mockedGet = vi.mocked(api.get)

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function response(path: string, page: number): NodeDataResponse {
  return {
    columns: ['path'],
    index: ['0'],
    rows: [{ path }],
    absolute_rows: [page * 50],
    total_rows: 100,
    page,
    page_size: 50,
    column_types: { path: 'Path' },
  }
}

function registerCanvases(): [CanvasId, CanvasId] {
  const canvasA = canvasIdFromPanelId('workflow:a')
  const canvasB = canvasIdFromPanelId('workflow:b')
  canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'a' })
  canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'b' })
  return [canvasA, canvasB]
}

describe('dataTable store canvas ownership', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    mockedGet.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('keeps response, page, loading, error, and pending state independent for identical node ids', async () => {
    vi.useFakeTimers()
    const [canvasA, canvasB] = registerCanvases()
    const store = useDataTableStore()
    const requestA = deferred<{ data: NodeDataResponse }>()
    const requestB = deferred<{ data: NodeDataResponse }>()
    mockedGet
      .mockReturnValueOnce(requestA.promise as any)
      .mockReturnValueOnce(requestB.promise as any)

    const fetchA = store.fetchCanvasNodeData(canvasA, 'shared', {
      page: 2,
      workflowName: 'a',
    })
    const fetchB = store.fetchCanvasNodeData(canvasB, 'shared', {
      page: 7,
      workflowName: 'b',
    })

    expect(store.getCanvasPageState(canvasA, 'shared').page).toBe(2)
    expect(store.getCanvasPageState(canvasB, 'shared').page).toBe(7)
    expect(store.isCanvasLoading(canvasA, 'shared')).toBe(true)
    expect(store.isCanvasLoading(canvasB, 'shared')).toBe(true)

    requestA.resolve({ data: response('/a.csv', 2) })
    await fetchA
    expect(store.getCanvasNodeData(canvasA, 'shared')?.rows[0]?.path).toBe('/a.csv')
    expect(store.isCanvasLoading(canvasA, 'shared')).toBe(false)
    expect(store.isCanvasLoading(canvasB, 'shared')).toBe(true)

    requestB.reject(new Error('B failed'))
    await fetchB
    expect(store.getCanvasError(canvasB, 'shared')).toBe('B failed')
    expect(store.getCanvasNodeData(canvasB, 'shared')).toBeUndefined()
    expect(store.getCanvasNodeData(canvasA, 'shared')?.rows[0]?.path).toBe('/a.csv')

    mockedGet.mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'B is preparing' } },
    })
    await store.fetchCanvasNodeData(canvasB, 'shared', {
      page: 8,
      workflowName: 'b',
    })

    expect(store.isCanvasPending(canvasB, 'shared')).toBe(true)
    expect(store.getCanvasError(canvasB, 'shared')).toBeNull()
    expect(store.isCanvasPending(canvasA, 'shared')).toBe(false)
    expect(store.getCanvasPageState(canvasA, 'shared').page).toBe(2)
  })

  it('does not abort, overwrite, or clear another canvas request for the same node', async () => {
    const [canvasA, canvasB] = registerCanvases()
    const store = useDataTableStore()
    const requestA1 = deferred<{ data: NodeDataResponse }>()
    const requestB = deferred<{ data: NodeDataResponse }>()
    const requestA2 = deferred<{ data: NodeDataResponse }>()
    const signals: AbortSignal[] = []
    mockedGet.mockImplementation((_url, config) => {
      signals.push(config!.signal as AbortSignal)
      if (signals.length === 1) return requestA1.promise as any
      if (signals.length === 2) return requestB.promise as any
      return requestA2.promise as any
    })

    const fetchA1 = store.fetchCanvasNodeData(canvasA, 'shared', { workflowName: 'a' })
    const fetchB = store.fetchCanvasNodeData(canvasB, 'shared', { workflowName: 'b' })
    const fetchA2 = store.fetchCanvasNodeData(canvasA, 'shared', { workflowName: 'a' })

    expect(signals[0].aborted).toBe(true)
    expect(signals[1].aborted).toBe(false)
    store.clearCanvasCache(canvasA, 'shared')
    expect(signals[2].aborted).toBe(true)
    expect(signals[1].aborted).toBe(false)

    requestA1.resolve({ data: response('/stale-a.csv', 0) })
    requestA2.resolve({ data: response('/cleared-a.csv', 0) })
    requestB.resolve({ data: response('/b.csv', 0) })
    await Promise.all([fetchA1, fetchA2, fetchB])

    expect(store.getCanvasNodeData(canvasA, 'shared')).toBeUndefined()
    expect(store.getCanvasNodeData(canvasB, 'shared')?.rows[0]?.path).toBe('/b.csv')
  })

  it('runs a canvas retry without canceling or replacing the other canvas request', async () => {
    vi.useFakeTimers()
    const [canvasA, canvasB] = registerCanvases()
    const store = useDataTableStore()
    const requestB = deferred<{ data: NodeDataResponse }>()
    let requestBSignal: AbortSignal | undefined
    let attemptsA = 0
    mockedGet.mockImplementation((_url, config) => {
      const workflowName = config?.params?.workflow_name
      if (workflowName === 'a') {
        attemptsA += 1
        if (attemptsA === 1) {
          return Promise.reject({
            response: { status: 409, data: { detail: 'A is preparing' } },
          }) as any
        }
        return Promise.resolve({ data: response('/retried-a.csv', 0) }) as any
      }
      requestBSignal = config!.signal as AbortSignal
      return requestB.promise as any
    })

    await store.fetchCanvasNodeData(canvasA, 'shared', { workflowName: 'a' })
    const fetchB = store.fetchCanvasNodeData(canvasB, 'shared', { workflowName: 'b' })
    expect(store.isCanvasPending(canvasA, 'shared')).toBe(true)
    expect(store.isCanvasLoading(canvasB, 'shared')).toBe(true)

    await vi.advanceTimersByTimeAsync(1_000)

    expect(attemptsA).toBe(2)
    expect(requestBSignal?.aborted).toBe(false)
    expect(store.getCanvasNodeData(canvasA, 'shared')?.rows[0]?.path).toBe('/retried-a.csv')
    expect(store.isCanvasLoading(canvasB, 'shared')).toBe(true)

    requestB.resolve({ data: response('/b.csv', 0) })
    await fetchB
  })

  it('keeps delayed fixed-canvas responses out of another active canvas and never falls back with no active canvas', async () => {
    const store = useDataTableStore()
    store.nodeDataCache.shared = response('/legacy.csv', 0)
    const [canvasA, canvasB] = registerCanvases()

    expect(store.getNodeData('shared')).toBeUndefined()
    expect(store.getPageState('shared')).toEqual({
      page: 0,
      pageSize: 50,
      sortBy: null,
      sortOrder: 'asc',
    })
    await store.fetchNodeData('shared')
    expect(mockedGet).not.toHaveBeenCalled()

    const requestA = deferred<{ data: NodeDataResponse }>()
    mockedGet
      .mockReturnValueOnce(requestA.promise as any)
      .mockResolvedValueOnce({ data: response('/b.csv', 0) } as any)
    canvasSessionRegistry.activate(canvasA)
    const fetchA = store.fetchNodeData('shared', { workflowName: 'a' })
    canvasSessionRegistry.activate(canvasB)
    await store.fetchNodeData('shared', { workflowName: 'b' })
    requestA.resolve({ data: response('/a.csv', 0) })
    await fetchA

    expect(store.getNodeData('shared')?.rows[0]?.path).toBe('/b.csv')
    canvasSessionRegistry.activate(canvasA)
    expect(store.getNodeData('shared')?.rows[0]?.path).toBe('/a.csv')

    store.releaseCanvas(canvasA)
    expect(store.getCanvasNodeData(canvasA, 'shared')).toBeUndefined()
    expect(store.getCanvasNodeData(canvasB, 'shared')?.rows[0]?.path).toBe('/b.csv')
  })
})
