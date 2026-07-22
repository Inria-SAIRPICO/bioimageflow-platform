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
  api: { get: vi.fn(), post: vi.fn() },
}))

const mockedPost = vi.mocked(api.post)

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
    unfiltered_total_rows: 100,
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
    mockedPost.mockReset()
  })

  afterEach(() => {
    useDataTableStore().setPreferredPageSize(250)
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('keeps response, page, loading, error, and pending state independent for identical node ids', async () => {
    vi.useFakeTimers()
    const [canvasA, canvasB] = registerCanvases()
    const store = useDataTableStore()
    const requestA = deferred<{ data: NodeDataResponse }>()
    const requestB = deferred<{ data: NodeDataResponse }>()
    mockedPost
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

    mockedPost.mockRejectedValueOnce({
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
    mockedPost.mockImplementation((_url, _body, config) => {
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
    mockedPost.mockImplementation((_url, body, config) => {
      const workflowName = (body as { workflow_name?: string })?.workflow_name
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
    const [canvasA, canvasB] = registerCanvases()

    expect(store.getNodeData('shared')).toBeUndefined()
    expect(store.nodeDataCache).toEqual({})
    expect(store.getPageState('shared')).toEqual({
      page: 0,
      pageSize: 250,
      sortBy: null,
      sortOrder: 'asc',
      filters: [],
    })
    await store.fetchNodeData('shared')
    expect(mockedPost).not.toHaveBeenCalled()

    const requestA = deferred<{ data: NodeDataResponse }>()
    mockedPost
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

  it('does not recreate a released canvas context from a delayed fixed-canvas action', async () => {
    const [canvasA] = registerCanvases()
    const store = useDataTableStore()
    mockedPost.mockResolvedValue({ data: response('/a.csv', 0) } as any)

    await store.fetchCanvasNodeData(canvasA, 'shared', { workflowName: 'a' })
    store.releaseCanvas(canvasA)
    await store.fetchCanvasNodeData(canvasA, 'shared', { workflowName: 'a' })

    expect(mockedPost).toHaveBeenCalledTimes(1)
    expect(store.getCanvasNodeData(canvasA, 'shared')).toBeUndefined()

    store.registerCanvas(canvasA)
    mockedPost.mockResolvedValueOnce({ data: response('/remounted-a.csv', 0) } as any)
    await store.fetchCanvasNodeData(canvasA, 'shared', { workflowName: 'a' })

    expect(mockedPost).toHaveBeenCalledTimes(2)
    expect(store.getCanvasNodeData(canvasA, 'shared')?.rows[0]?.path).toBe(
      '/remounted-a.csv',
    )
  })

  it('keeps upstream depth as per-canvas session state', () => {
    const [canvasA, canvasB] = registerCanvases()
    const store = useDataTableStore()
    canvasSessionRegistry.activate(canvasA)
    store.setUpstreamDepth(3)
    expect(store.upstreamDepth).toBe(3)

    canvasSessionRegistry.activate(canvasB)
    expect(store.upstreamDepth).toBe(0)
    store.setUpstreamDepth(1)

    canvasSessionRegistry.activate(canvasA)
    expect(store.upstreamDepth).toBe(3)
  })

  it('uses the preferred page size and sends node filters through the typed query', async () => {
    const [canvasA] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    store.setPreferredPageSize(100)
    mockedPost.mockResolvedValue({ data: response('/filtered.csv', 0) } as any)

    await store.fetchNodeData('node', { workflowName: 'a' })
    await store.setFilters('node', [
      { column: 'path', operator: 'contains', value: 'filtered' },
    ], { workflowName: 'a' })

    expect(mockedPost.mock.calls[0][0]).toBe('/api/v1/nodes/node/data/query')
    expect(mockedPost.mock.calls[0][1]).toMatchObject({ page_size: 100, filters: [] })
    expect(mockedPost.mock.calls[1][1]).toMatchObject({
      page: 0,
      filters: [{ column: 'path', operator: 'contains', value: 'filtered' }],
    })
  })

  it('cancels stale consolidated queries and ignores their responses', async () => {
    const [canvasA] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    const first = deferred<{ data: any }>()
    const second = deferred<{ data: any }>()
    const signals: AbortSignal[] = []
    mockedPost.mockImplementation((_url, _body, config) => {
      signals.push(config!.signal as AbortSignal)
      return (signals.length === 1 ? first.promise : second.promise) as any
    })
    const request = {
      workflow_id: 'a',
      sources: [{ node_id: 'node', role: 'anchor' as const, label: 'Node', column_aliases: {} }],
    }

    const firstFetch = store.fetchProjection(request)
    const secondFetch = store.fetchProjection(request)
    expect(signals[0].aborted).toBe(true)
    second.resolve({ data: {
      mode: 'stacked',
      sources: request.sources,
      reason: 'new',
      message: 'new response',
    } })
    await secondFetch
    first.resolve({ data: {
      mode: 'stacked',
      sources: request.sources,
      reason: 'old',
      message: 'stale response',
    } })
    await firstFetch

    expect(store.projection?.mode).toBe('stacked')
    expect(store.projection?.mode === 'stacked' ? store.projection.message : '').toBe('new response')
  })

  it('requeries the full projection when sorting or paging changes', async () => {
    const [canvasA] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    mockedPost.mockResolvedValue({ data: {
      mode: 'merged',
      sources: [],
      columns: [],
      rows: [],
      total_rows: 0,
      page: 0,
      page_size: 50,
    } } as any)
    await store.fetchProjection({
      workflow_id: 'a',
      sources: [{ node_id: 'node', role: 'anchor', label: 'Node', column_aliases: {} }],
    })
    await store.setProjectionSort('s0:value', 'desc')
    await store.setProjectionFilters([{ column: 's0:value', operator: 'gte', value: 2 }])
    await store.setProjectionPage(2)

    expect(mockedPost.mock.calls[1][1]).toMatchObject({
      page: 0,
      sort_by: 's0:value',
      sort_order: 'desc',
    })
    expect(mockedPost.mock.calls[2][1]).toMatchObject({
      page: 0,
      filters: [{ column: 's0:value', operator: 'gte', value: 2 }],
    })
    expect(mockedPost.mock.calls[3][1]).toMatchObject({
      page: 2,
      sort_by: 's0:value',
      sort_order: 'desc',
      filters: [{ column: 's0:value', operator: 'gte', value: 2 }],
    })
  })

  it('retries a consolidated query while immutable result data is being exposed', async () => {
    vi.useFakeTimers()
    const [canvasA] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    mockedPost
      .mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Preparing data' } } })
      .mockResolvedValueOnce({ data: {
        mode: 'merged',
        sources: [],
        columns: [],
        rows: [],
        total_rows: 0,
        page: 0,
        page_size: 50,
      } } as any)

    await store.fetchProjection({
      workflow_id: 'a',
      sources: [{ node_id: 'node', role: 'anchor', label: 'Node', column_aliases: {} }],
    })
    expect(store.projectionLoading).toBe(true)
    expect(store.projectionError).toBeNull()

    await vi.advanceTimersByTimeAsync(1_000)
    expect(mockedPost).toHaveBeenCalledTimes(2)
    expect(store.projection?.mode).toBe('merged')
    expect(store.projectionLoading).toBe(false)
  })

  it('downloads merged CSV with the current source and sort contract', async () => {
    const [canvasA] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    const merged = {
      mode: 'merged',
      sources: [],
      columns: [],
      rows: [],
      total_rows: 0,
      page: 0,
      page_size: 50,
    }
    mockedPost
      .mockResolvedValueOnce({ data: merged } as any)
      .mockResolvedValueOnce({ data: merged } as any)
      .mockResolvedValueOnce({ data: new Blob(['csv']) } as any)
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:csv'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    await store.fetchProjection({
      workflow_id: 'a',
      sources: [{ node_id: 'node', role: 'anchor', label: 'Node', column_aliases: {} }],
    })
    await store.setProjectionSort('s0:value', 'desc')
    await store.downloadProjectionCsv()

    expect(mockedPost.mock.calls[2][0]).toBe('/api/v1/data-table/csv')
    expect(mockedPost.mock.calls[2][1]).toMatchObject({
      workflow_id: 'a',
      sort_by: 's0:value',
      sort_order: 'desc',
    })
    expect(mockedPost.mock.calls[2][1]).not.toHaveProperty('page')
  })
})
