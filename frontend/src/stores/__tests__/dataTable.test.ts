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
    identity_status: 'legacy_unpinned',
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
      response: { status: 409, data: { error: 'result_pending', detail: 'B is preparing' } },
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
            response: { status: 409, data: { error: 'result_pending', detail: 'A is preparing' } },
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

  it('pins the captured node result across sorting and pagination', async () => {
    const [canvasA] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    const sourceIdentity = {
      run_id: 'run-1', node_key: 'node', result_key: 'result-1', record_id: 'record-1',
    }
    mockedPost.mockResolvedValue({ data: {
      ...response('/captured.tif', 0),
      source_identity: sourceIdentity,
      identity_status: 'captured',
    } } as any)

    await store.fetchNodeData('node', { workflowName: 'a' })
    await store.setSort('node', 'path', 'desc', { workflowName: 'a' })
    await store.setPage('node', 1, { workflowName: 'a' })

    expect(mockedPost.mock.calls[0][1]).toMatchObject({ result_identity: null })
    expect(mockedPost.mock.calls[1][1]).toMatchObject({ result_identity: sourceIdentity })
    expect(mockedPost.mock.calls[2][1]).toMatchObject({ result_identity: sourceIdentity })
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
    const sourceIdentity = {
      run_id: 'run-1', node_key: 'node', result_key: 'result-1', record_id: 'record-1',
    }
    mockedPost.mockResolvedValue({ data: {
      mode: 'merged',
      sources: [{
        node_id: 'node', role: 'anchor', label: 'Node', column_aliases: {},
        result_identity: sourceIdentity,
      }],
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
      sources: [expect.objectContaining({ result_identity: sourceIdentity })],
    })
    expect(mockedPost.mock.calls[2][1]).toMatchObject({
      page: 0,
      filters: [{ column: 's0:value', operator: 'gte', value: 2 }],
      sources: [expect.objectContaining({ result_identity: sourceIdentity })],
    })
    expect(mockedPost.mock.calls[3][1]).toMatchObject({
      page: 2,
      sort_by: 's0:value',
      sort_order: 'desc',
      filters: [{ column: 's0:value', operator: 'gte', value: 2 }],
      sources: [expect.objectContaining({ result_identity: sourceIdentity })],
    })

    const sourceRequest = {
      workflow_id: 'a',
      sources: [{ node_id: 'node', role: 'anchor' as const, label: 'Node', column_aliases: {} }],
    }
    await store.fetchProjection(sourceRequest)
    await store.fetchProjection(sourceRequest, { captureLatest: true })
    expect(mockedPost.mock.calls[4][1]).toMatchObject({
      sources: [expect.objectContaining({ result_identity: sourceIdentity })],
    })
    expect(mockedPost.mock.calls[5][1]).toMatchObject({
      sources: [expect.objectContaining({ result_identity: null })],
    })
  })

  it('retries a consolidated query while immutable result data is being exposed', async () => {
    vi.useFakeTimers()
    const [canvasA] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    mockedPost
      .mockRejectedValueOnce({ response: { status: 409, data: { error: 'result_pending', detail: 'Preparing data' } } })
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

  it('shows permanent consolidated conflicts immediately without polling', async () => {
    vi.useFakeTimers()
    const [canvas] = registerCanvases()
    canvasSessionRegistry.activate(canvas)
    mockedPost.mockRejectedValue({ response: { status: 409, data: { error: 'result_unavailable', detail: 'Unsupported saved result; re-run this node' } } })
    const store = useDataTableStore()
    await store.fetchProjection({
      workflow_id: 'a', sources: [{ node_id: 'node', role: 'anchor', label: 'Node', column_aliases: {} }],
    })
    expect(store.projectionLoading).toBe(false)
    expect(store.projectionError).toBe('Unsupported saved result; re-run this node')
    await vi.advanceTimersByTimeAsync(60_000)
    expect(mockedPost).toHaveBeenCalledTimes(1)
  })

  it('shows permanent individual conflicts immediately without polling', async () => {
    vi.useFakeTimers()
    const [canvas] = registerCanvases()
    mockedPost.mockRejectedValue({ response: { status: 409, data: { detail: 'Captured result identity no longer matches' } } })
    const store = useDataTableStore()
    await store.fetchCanvasNodeData(canvas, 'node', { workflowName: 'a' })
    expect(store.isCanvasPending(canvas, 'node')).toBe(false)
    expect(store.isCanvasLoading(canvas, 'node')).toBe(false)
    expect(store.getCanvasError(canvas, 'node')).toBe('Captured result identity no longer matches')
    await vi.advanceTimersByTimeAsync(60_000)
    expect(mockedPost).toHaveBeenCalledTimes(1)
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

  it('publishes one inspection epoch only after an unchanged-ID refresh succeeds', async () => {
    const [canvasA] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    const identity = { run_id: 'run-A', node_key: 'node', result_key: 'rk-A', record_id: 'rec-A' }
    const request = { workflow_id: 'a', sources: [{ node_id: 'node', role: 'anchor' as const, label: 'Node', column_aliases: {} }] }
    const data = { mode: 'merged', sources: [{ ...request.sources[0], result_identity: identity }],
      columns: [], rows: [], total_rows: 0, unfiltered_total_rows: 0, page: 0, page_size: 250 }
    mockedPost.mockResolvedValueOnce({ data } as any)
    await store.fetchProjection(request)
    const epoch = store.inspectionKey
    const pendingRefresh = deferred<{ data: any }>()
    mockedPost.mockReturnValueOnce(pendingRefresh.promise as any)
    const refresh = store.fetchProjection(request, { captureLatest: true })
    expect(store.inspectionKey).toBe(epoch)
    expect(store.projection).toEqual(data)
    pendingRefresh.resolve({ data })
    await refresh
    expect(Number(store.inspectionKey.split(':')[1])).toBe(Number(epoch.split(':')[1]) + 1)
    const accepted = store.inspectionKey
    mockedPost.mockRejectedValueOnce(new Error('Refresh unavailable'))
    await store.fetchProjection(request, { captureLatest: true })
    expect(store.inspectionKey).toBe(accepted)
    expect(store.projection).toEqual(data)
  })

  it('fences pending old-mode responses and preserves pins and sort across a mode change', async () => {
    const [canvasA] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    const identity = { run_id: 'run-A', node_key: 'node', result_key: 'rk-A', record_id: 'rec-A' }
    const request = { workflow_id: 'a', sources: [{ node_id: 'node', role: 'anchor' as const, label: 'Node', column_aliases: {} }] }
    const data = { mode: 'merged', sources: [{ ...request.sources[0], result_identity: identity }],
      columns: [], rows: [], total_rows: 0, unfiltered_total_rows: 0, page: 0, page_size: 250 }
    mockedPost.mockResolvedValue({ data } as any)
    await store.fetchProjection(request)
    await store.setProjectionFilters([{ column: 'value', operator: 'equals', value: 1 }])
    await store.setProjectionSort('value', 'desc')
    const epoch = store.inspectionKey
    const obsolete = deferred<{ data: any }>()
    mockedPost.mockReturnValueOnce(obsolete.promise as any)
    const oldRead = store.setProjectionPage(1)
    const oldSignal = mockedPost.mock.calls[mockedPost.mock.calls.length - 1]![2]!.signal as AbortSignal
    store.setBrowsingMode('continuous')
    expect(oldSignal.aborted).toBe(true)
    obsolete.resolve({ data: { ...data, total_rows: 1000 } })
    await oldRead
    expect(store.projection?.mode === 'merged' && store.projection.total_rows).toBe(0)
    await store.fetchProjection(request, { preserveQuery: true })
    expect(mockedPost.mock.calls[mockedPost.mock.calls.length - 1]![1]).toMatchObject({
      page: 0, page_size: 32, sort_by: 'value', sort_order: 'desc',
      filters: [{ column: 'value', operator: 'equals', value: 1 }],
      sources: [{ ...request.sources[0], result_identity: identity }],
    })
    expect(store.inspectionKey).toBe(epoch)
  })

  it('keeps captured stacked identities when downloading a displayed individual result', async () => {
    const [canvasA] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    const identity = { run_id: 'run-A', node_key: 'node', result_key: 'rk-A', record_id: 'rec-A' }
    const request = { workflow_id: 'a', sources: [{ node_id: 'node', role: 'anchor' as const, label: 'Node', column_aliases: {} }] }
    mockedPost.mockResolvedValueOnce({ data: { mode: 'stacked', sources: [{ ...request.sources[0], result_identity: identity }], reason: 'independent', message: 'Separate' } } as any)
    await store.fetchProjection(request)
    const epoch = store.inspectionKey
    mockedPost.mockResolvedValueOnce({ data: { ...response('/captured.tif', 0), source_identity: identity, identity_status: 'captured' } } as any)
    await store.fetchNodeData('node', { workflowName: 'a', resultIdentity: identity })
    expect(store.inspectionKey).toBe(epoch)
    mockedPost.mockResolvedValueOnce({ data: new Blob(['csv']) } as any)
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:csv') })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    await store.downloadCsv('node', 'a')
    expect(mockedPost.mock.calls[2]![1]).toMatchObject({ result_identity: identity })
  })

  it('uses the preferred and local page sizes for a legacy merged fallback in continuous mode', async () => {
    const [canvasA] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    store.setPreferredPageSize(250)
    store.setBrowsingMode('continuous')
    const captured = { run_id: 'run-A', node_key: 'captured', result_key: 'rk-A', record_id: 'rec-A' }
    const request = { workflow_id: 'a', sources: [
      { node_id: 'captured', role: 'anchor' as const, label: 'Captured', column_aliases: {} },
      { node_id: 'legacy', role: 'context' as const, label: 'Legacy', column_aliases: {} },
    ] }
    mockedPost.mockImplementation(async (_url, body: any) => ({ data: {
      mode: 'merged', sources: body.sources.map((source: any) => ({ ...source,
        result_identity: source.node_id === 'captured' ? captured : null })),
      columns: [], rows: [{ index: '0', values: {}, source_rows: { captured: 0, legacy: 0 } }],
      total_rows: 1, unfiltered_total_rows: 1, page: body.page, page_size: body.page_size,
    } }) as any)
    await store.fetchProjection(request)
    expect(mockedPost.mock.calls.map(call => (call[1] as any).page_size)).toEqual([32, 250])
    expect((mockedPost.mock.calls[1]![1] as any).sources.map((source: any) => source.result_identity)).toEqual([captured, null])
    expect(store.projectionPage.pageSize).toBe(250)
    expect(store.isContinuous()).toBe(false)
    const acceptedEpoch = store.inspectionKey
    await store.setProjectionPage(0, 25)
    expect(mockedPost.mock.calls).toHaveLength(3)
    expect(mockedPost.mock.calls[2]![1]).toMatchObject({ page_size: 25 })
    expect(store.projectionPage.pageSize).toBe(25)
    expect(store.inspectionKey).toBe(acceptedEpoch)
    await store.fetchProjection(request, { preserveQuery: true })
    expect(mockedPost.mock.calls).toHaveLength(4)
    expect(mockedPost.mock.calls[3]![1]).toMatchObject({ page_size: 25 })
  })

  it('uses real paginator sizes for unknown and known legacy individual results in continuous mode', async () => {
    const [canvasA, canvasB] = registerCanvases()
    canvasSessionRegistry.activate(canvasA)
    const store = useDataTableStore()
    store.setPreferredPageSize(250)
    store.setBrowsingMode('continuous')
    mockedPost.mockImplementation(async (_url, body: any) => ({ data: {
      ...response('/legacy.tif', body.page), page_size: body.page_size,
      total_rows: 1, unfiltered_total_rows: 1, source_identity: null,
    } }) as any)
    await store.fetchNodeData('node', { workflowName: 'a' })
    expect(mockedPost.mock.calls.map(call => (call[1] as any).page_size)).toEqual([32, 250])
    expect(store.getPageState('node').pageSize).toBe(250)
    expect(store.isContinuous('node')).toBe(false)
    const acceptedEpoch = store.inspectionKey
    await store.setPageSize('node', 25, { workflowName: 'a' })
    expect(mockedPost.mock.calls).toHaveLength(3)
    expect(mockedPost.mock.calls[2]![1]).toMatchObject({ page_size: 25 })
    expect(store.getPageState('node').pageSize).toBe(25)
    expect(store.inspectionKey).toBe(acceptedEpoch)
    await store.fetchCanvasNodeData(canvasB, 'node', { workflowName: 'b', pageSize: 25 })
    expect(mockedPost.mock.calls.slice(3).map(call => (call[1] as any).page_size)).toEqual([32, 25])
    expect(store.getCanvasPageState(canvasB, 'node').pageSize).toBe(25)
  })
})
