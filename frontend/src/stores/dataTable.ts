import { computed, reactive, ref, shallowReactive } from 'vue'
import { createTableWindow, CONTINUOUS_BLOCK_SIZE, type TableWindow } from '@/composables/tableWindow'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { NodeDataResponse, ResultArtifactIdentity, ViewerSpec } from '@/api/types'
import { apiErrorMessage } from '@/utils/apiError'
import {
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'

export interface DataTablePageState {
  page: number
  pageSize: number
  sortBy: string | null
  sortOrder: 'asc' | 'desc'
  filters: DataTableFilter[]
}

export type DataTableFilterOperator =
  | 'contains'
  | 'starts_with'
  | 'equals'
  | 'not_equals'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'between'
  | 'is_empty'
  | 'is_not_empty'

export interface DataTableFilter {
  column: string
  operator: DataTableFilterOperator
  value?: string | number | boolean | null
  second_value?: string | number | boolean | null
}

export interface DataTableSourceRequest {
  node_id: string
  role: 'anchor' | 'context'
  label: string
  tool_name?: string | null
  columns?: string[] | null
  column_aliases: Record<string, string>
  result_identity?: ResultArtifactIdentity | null
}

export interface ConsolidatedDataTableColumn {
  id: string
  label: string
  type: string
  source_node_id: string
  source_column: string
  viewer: ViewerSpec | null
  viewer_status: 'captured' | 'legacy_unpinned'
}

export interface ConsolidatedDataTableRow {
  index: string
  values: Record<string, unknown>
  source_rows: Record<string, number>
}

export interface MergedDataTableResponse {
  mode: 'merged'
  sources: DataTableSourceRequest[]
  columns: ConsolidatedDataTableColumn[]
  rows: ConsolidatedDataTableRow[]
  total_rows: number
  unfiltered_total_rows: number
  page: number
  page_size: number
}

export interface StackedDataTableResponse {
  mode: 'stacked'
  sources: DataTableSourceRequest[]
  reason: string
  message: string
}

export type DataTableProjectionResponse = MergedDataTableResponse | StackedDataTableResponse

export interface DataTableProjectionRequest {
  workflow_id: string | null
  sources: DataTableSourceRequest[]
}

interface FetchOpts {
  toolName?: string | null
  workflowName?: string | null
  page?: number
  pageSize?: number
  sortBy?: string | null
  sortOrder?: 'asc' | 'desc'
  filters?: DataTableFilter[]
  retryAttempt?: number
  captureLatest?: boolean
  resultIdentity?: ResultArtifactIdentity | null
}

interface DataTableState {
  nodeDataCache: Record<string, NodeDataResponse>
  paginationState: Record<string, DataTablePageState>
  loading: Record<string, boolean>
  errors: Record<string, string | null>
  pending: Record<string, boolean>
  upstreamDepth: number
  projection: DataTableProjectionResponse | null
  projectionRequest: DataTableProjectionRequest | null
  projectionPage: DataTablePageState
  projectionLoading: boolean
  projectionError: string | null
  inspectionRevision: number
  windowRevision: number
}

interface DataTableContext {
  readonly state: DataTableState
  readonly inflightControllers: Map<string, AbortController>
  readonly requestIds: Map<string, number>
  readonly retryTimers: Map<string, ReturnType<typeof setTimeout>>
  projectionController: AbortController | null
  projectionRetryTimer: ReturnType<typeof setTimeout> | null
  projectionRequestId: number
  released: boolean
  readonly inspectionOwner: number
  readonly windows: Map<string, TableWindow<NodeDataResponse | MergedDataTableResponse>>
  readonly nodeIdentities: Map<string, ResultArtifactIdentity | null>
  readonly nodeOptions: Map<string, FetchOpts>
}

const EMPTY_NODE_DATA = Object.freeze({}) as Record<string, NodeDataResponse>
const EMPTY_PAGINATION = Object.freeze({}) as Record<string, DataTablePageState>
const EMPTY_FLAGS = Object.freeze({}) as Record<string, boolean>
const EMPTY_ERRORS = Object.freeze({}) as Record<string, string | null>
let preferredPageSize = 250
let inspectionOwner = 0

function defaultPageState(): DataTablePageState {
  return {
    page: 0,
    pageSize: preferredPageSize,
    sortBy: null,
    sortOrder: 'asc',
    filters: [],
  }
}

function createContext(): DataTableContext {
  return {
    state: reactive({
      nodeDataCache: {},
      paginationState: {},
      loading: {},
      errors: {},
      pending: {},
      upstreamDepth: 0,
      projection: null,
      projectionRequest: null,
      projectionPage: defaultPageState(),
      projectionLoading: false,
      projectionError: null,
      inspectionRevision: 0,
      windowRevision: 0,
    }) as DataTableState,
    inflightControllers: new Map(),
    requestIds: new Map(),
    retryTimers: new Map(),
    projectionController: null,
    projectionRetryTimer: null,
    projectionRequestId: 0,
    released: false,
    inspectionOwner: ++inspectionOwner,
    windows: new Map(),
    nodeIdentities: new Map(),
    nodeOptions: new Map(),
  }
}

function errorMessage(exc: unknown): string {
  return apiErrorMessage(exc)
}

function errorStatus(exc: unknown): number | null {
  if (typeof exc === 'object' && exc !== null && 'response' in exc) {
    const response = (exc as { response?: { status?: number } }).response
    return response?.status ?? null
  }
  return null
}

function isRetryableResultConflict(exc: unknown): boolean {
  if (errorStatus(exc) !== 409) return false
  const response = (exc as { response?: { data?: { error?: unknown } } }).response
  return response?.data?.error === 'result_pending'
}

function isCanceled(exc: unknown): boolean {
  const maybeCanceled = exc as { name?: string; code?: string }
  return maybeCanceled.name === 'CanceledError' || maybeCanceled.code === 'ERR_CANCELED'
}

const NOT_READY_RETRY_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 15_000]

async function readTableBlock<T>(url: string, body: unknown, signal: AbortSignal): Promise<T> {
  for (let attempt = 0; ; attempt += 1) {
    if (signal.aborted) throw new DOMException('Table request retired', 'AbortError')
    try {
      return (await api.post<T>(url, body, { signal })).data
    } catch (error) {
      if (!isRetryableResultConflict(error) || attempt >= NOT_READY_RETRY_DELAYS_MS.length) throw new Error(errorMessage(error))
      await new Promise<void>((resolve, reject) => {
        const abort = () => { clearTimeout(timer); reject(new DOMException('Table request retired', 'AbortError')) }
        const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, NOT_READY_RETRY_DELAYS_MS[attempt])
        signal.addEventListener('abort', abort, { once: true })
        if (signal.aborted) abort()
      })
    }
  }
}

export const useDataTableStore = defineStore('dataTable', () => {
  const browsingMode = ref<'paginated' | 'continuous'>('paginated')
  const canvasContexts = shallowReactive(new Map<CanvasId, DataTableContext>())
  const releasedCanvasIds = new Set<CanvasId>()

  function contextForCanvas(canvasId: CanvasId): DataTableContext | null {
    if (releasedCanvasIds.has(canvasId)) return null
    const existing = canvasContexts.get(canvasId)
    if (existing) return existing
    const created = createContext()
    canvasContexts.set(canvasId, created)
    return created
  }

  function registerCanvas(canvasId: CanvasId): void {
    releasedCanvasIds.delete(canvasId)
    if (!canvasContexts.has(canvasId)) {
      canvasContexts.set(canvasId, createContext())
    }
  }

  function existingCanvasContext(canvasId: CanvasId): DataTableContext | null {
    return canvasContexts.get(canvasId) ?? null
  }

  function activeContext(create: boolean): DataTableContext | null {
    const canvasId = canvasSessionRegistry.activeCanvasId.value
    if (canvasId !== null) {
      return create
        ? contextForCanvas(canvasId)
        : existingCanvasContext(canvasId)
    }
    return null
  }

  const nodeDataCache = computed(() => (
    activeContext(false)?.state.nodeDataCache ?? EMPTY_NODE_DATA
  ))
  const paginationState = computed(() => (
    activeContext(false)?.state.paginationState ?? EMPTY_PAGINATION
  ))
  const loading = computed(() => activeContext(false)?.state.loading ?? EMPTY_FLAGS)
  const errors = computed(() => activeContext(false)?.state.errors ?? EMPTY_ERRORS)
  const pending = computed(() => activeContext(false)?.state.pending ?? EMPTY_FLAGS)
  const upstreamDepth = computed(() => activeContext(false)?.state.upstreamDepth ?? 0)
  const projection = computed(() => activeContext(false)?.state.projection ?? null)
  const projectionLoading = computed(() => activeContext(false)?.state.projectionLoading ?? false)
  const projectionError = computed(() => activeContext(false)?.state.projectionError ?? null)
  const projectionPage = computed(() => activeContext(false)?.state.projectionPage ?? defaultPageState())

  const inspectionKey = computed(() => {
    const context = activeContext(false)
    return context ? `${context.inspectionOwner}:${context.state.inspectionRevision}` : 'unregistered'
  })

  function retireInspection(context: DataTableContext): void {
    context.state.inspectionRevision += 1
  }

  function resetWindow(context: DataTableContext, key: string): void {
    context.windows.get(key)?.reset()
    context.windows.delete(key)
    context.state.windowRevision += 1
  }

  function windowFor(context: DataTableContext, key: string) {
    let window = context.windows.get(key)
    if (!window) {
      window = createTableWindow<NodeDataResponse | MergedDataTableResponse>()
      context.windows.set(key, window)
      context.state.windowRevision += 1
    }
    return window
  }

  function setBrowsingMode(mode: 'paginated' | 'continuous'): void {
    if (browsingMode.value === mode) return
    browsingMode.value = mode
    for (const context of canvasContexts.values()) {
      invalidateProjection(context)
      for (const nodeId of context.requestIds.keys()) {
        invalidateRequest(context, nodeId)
        context.state.loading[nodeId] = false
        context.state.pending[nodeId] = false
      }
      for (const window of context.windows.values()) window.reset()
      context.windows.clear()
      context.state.windowRevision += 1

    }
  }

  function setUpstreamDepth(value: number): void {
    const context = activeContext(true)
    if (context) context.state.upstreamDepth = Math.max(0, Math.floor(value))
  }

  function invalidateProjection(context: DataTableContext): void {
    context.projectionRequestId += 1
    context.projectionController?.abort()
    context.projectionController = null
    if (context.projectionRetryTimer !== null) {
      clearTimeout(context.projectionRetryTimer)
      context.projectionRetryTimer = null
    }
    context.state.projectionLoading = false
  }

  function paginatedSize(pageSize?: number): number {
    return pageSize && pageSize !== CONTINUOUS_BLOCK_SIZE ? pageSize : preferredPageSize
  }

  function knownLegacyProjection(context: DataTableContext, request: DataTableProjectionRequest): boolean {
    return request.sources.some(source => !source.result_identity
      && context.state.projectionRequest?.sources.some(previous => previous.node_id === source.node_id && !previous.result_identity))
  }

  async function fetchProjectionInContext(
    context: DataTableContext,
    request: DataTableProjectionRequest,
    pageState: DataTablePageState = context.state.projectionPage,
    retryAttempt = 0,
    newInspection = false,
    fallbackPageSize = paginatedSize(pageState.pageSize),
  ): Promise<void> {
    if (context.released) return
    invalidateProjection(context)
    context.windows.get('projection')?.pause()
    const controller = new AbortController()
    context.projectionController = controller
    const requestId = context.projectionRequestId
    context.state.projectionPage = { ...pageState }
    context.state.projectionLoading = true
    context.state.projectionError = null
    let retryScheduled = false
    try {
      const read = (sources: DataTableSourceRequest[]) => api.post<DataTableProjectionResponse>(
        '/api/v1/data-table/query',
        {
          ...request,
          sources,
          page: pageState.page,
          page_size: pageState.pageSize,
          sort_by: pageState.sortBy,
          sort_order: pageState.sortOrder,
          filters: pageState.filters,
        },
        { signal: controller.signal },
      )
      let { data } = await read(request.sources)
      // Publish one coherent page/inspection only after the captured vector
      // determines whether this is a continuous window or legacy pagination.
      for (let correction = 0; correction < 2 && data.mode === 'merged'
        && browsingMode.value === 'continuous'; correction += 1) {
        if (context.released || context.projectionRequestId !== requestId) return
        const size = data.sources.every(source => source.result_identity) ? CONTINUOUS_BLOCK_SIZE : fallbackPageSize
        if (size === pageState.pageSize) break
        pageState = { ...pageState, pageSize: size }
        request = { ...request, sources: data.sources.map(source => ({ ...source })) }
        data = (await read(request.sources)).data
      }
      if (!context.released && context.projectionRequestId === requestId) {
        context.state.projectionPage = { ...pageState }
        resetWindow(context, 'projection')
        context.state.projection = data
        const previous = context.state.projectionRequest?.sources.map(source => source.result_identity)
        const next = data.sources.map(source => source.result_identity)
        if (newInspection || JSON.stringify(previous) !== JSON.stringify(next)) retireInspection(context)
        context.state.projectionRequest = { ...request, sources: data.sources.map(source => ({ ...source })) }
        if (browsingMode.value === 'continuous' && data.mode === 'merged' && data.sources.every(source => source.result_identity)) {
          windowFor(context, 'projection').seed(pageState.page, data)
        }
      }
    } catch (exc: unknown) {
      if (!isCanceled(exc) && !context.released && context.projectionRequestId === requestId) {
        if (isRetryableResultConflict(exc) && retryAttempt < NOT_READY_RETRY_DELAYS_MS.length) {
          retryScheduled = true
          const timer = setTimeout(() => {
            if (context.projectionRetryTimer === timer) context.projectionRetryTimer = null
            if (!context.released && context.projectionRequestId === requestId) {
              void fetchProjectionInContext(context, request, pageState, retryAttempt + 1, newInspection, fallbackPageSize)
            }
          }, NOT_READY_RETRY_DELAYS_MS[retryAttempt])
          context.projectionRetryTimer = timer
        } else {
          if (!newInspection) context.state.projection = null
          context.state.projectionError = errorMessage(exc)
        }
      }
    } finally {
      if (!context.released && context.projectionRequestId === requestId) {
        context.state.projectionLoading = retryScheduled
        context.projectionController = null
      }
    }
  }

  function fetchProjection(
    request: DataTableProjectionRequest,
    options: { captureLatest?: boolean; newInspection?: boolean; preserveQuery?: boolean } = {},
  ): Promise<void> {
    const context = activeContext(true)
    if (!context) return Promise.resolve()
    const retainedIdentities = options.captureLatest
      ? new Map<string, ResultArtifactIdentity>()
      : new Map(
          (context.state.projectionRequest?.sources ?? [])
            .filter(source => source.result_identity)
            .map(source => [source.node_id, source.result_identity!]),
        )
    const selectedRequest = {
      ...request,
      sources: request.sources.map(source => ({
        ...source,
        result_identity: source.result_identity ?? retainedIdentities.get(source.node_id) ?? null,
      })),
    }
    const fallbackSize = options.preserveQuery ? paginatedSize(context.state.projectionPage.pageSize) : preferredPageSize
    return fetchProjectionInContext(context, selectedRequest, {
      ...(options.preserveQuery ? context.state.projectionPage : defaultPageState()), page: 0,
      pageSize: browsingMode.value === 'continuous' && (options.captureLatest || !knownLegacyProjection(context, selectedRequest))
        ? CONTINUOUS_BLOCK_SIZE : fallbackSize,
    }, 0, options.captureLatest || options.newInspection, fallbackSize)
  }

  function clearProjection(): void {
    const context = activeContext(false)
    if (!context) return
    invalidateProjection(context)
    resetWindow(context, 'projection')
    context.state.projection = null
    context.state.projectionRequest = null
    context.state.projectionError = null
    context.state.projectionPage = defaultPageState()
  }

  function setProjectionPage(page: number, pageSize?: number): Promise<void> {
    const context = activeContext(true)
    if (!context?.state.projectionRequest) return Promise.resolve()
    return fetchProjectionInContext(context, context.state.projectionRequest, {
      ...context.state.projectionPage,
      page: pageSize === undefined ? page : 0,
      pageSize: browsingMode.value === 'continuous' && !knownLegacyProjection(context, context.state.projectionRequest)
        ? CONTINUOUS_BLOCK_SIZE : pageSize ?? context.state.projectionPage.pageSize,
    })
  }

  function setProjectionSort(sortBy: string | null, sortOrder: 'asc' | 'desc'): Promise<void> {
    const context = activeContext(true)
    if (!context?.state.projectionRequest) return Promise.resolve()
    return fetchProjectionInContext(context, context.state.projectionRequest, {
      ...context.state.projectionPage,
      page: 0,
      sortBy,
      sortOrder,
    })
  }

  function setProjectionFilters(filters: DataTableFilter[]): Promise<void> {
    const context = activeContext(true)
    if (!context?.state.projectionRequest) return Promise.resolve()
    return fetchProjectionInContext(context, context.state.projectionRequest, {
      ...context.state.projectionPage,
      page: 0,
      filters: [...filters],
    })
  }

  async function downloadProjectionCsv(): Promise<void> {
    const context = activeContext(false)
    const request = context?.state.projectionRequest
    if (!context || !request) return
    context.state.projectionError = null
    try {
      const { data } = await api.post(
        '/api/v1/data-table/csv',
        {
          ...request,
          sort_by: context.state.projectionPage.sortBy,
          sort_order: context.state.projectionPage.sortOrder,
          filters: context.state.projectionPage.filters,
        },
        { responseType: 'blob' },
      )
      const href = URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href = href
      link.download = 'data-table.csv'
      link.style.display = 'none'
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(href)
    } catch (exc: unknown) {
      context.state.projectionError = errorMessage(exc)
    }
  }

  function stateFor(context: DataTableContext, nodeId: string): DataTablePageState {
    if (!context.state.paginationState[nodeId]) {
      context.state.paginationState[nodeId] = defaultPageState()
    }
    return context.state.paginationState[nodeId]
  }

  function clearRetry(context: DataTableContext, nodeId: string): void {
    const timer = context.retryTimers.get(nodeId)
    if (timer !== undefined) {
      clearTimeout(timer)
      context.retryTimers.delete(nodeId)
    }
  }

  function isCurrentRequest(
    context: DataTableContext,
    nodeId: string,
    requestId: number,
  ): boolean {
    return !context.released && context.requestIds.get(nodeId) === requestId
  }

  function invalidateRequest(context: DataTableContext, nodeId: string): void {
    context.requestIds.set(nodeId, (context.requestIds.get(nodeId) ?? 0) + 1)
    clearRetry(context, nodeId)
    context.inflightControllers.get(nodeId)?.abort()
    context.inflightControllers.delete(nodeId)
  }

  function scheduleNotReadyRetry(
    context: DataTableContext,
    nodeId: string,
    opts: FetchOpts,
    retryAttempt: number,
    requestId: number,
    detail: string,
  ): void {
    clearRetry(context, nodeId)
    const delay = NOT_READY_RETRY_DELAYS_MS[retryAttempt]
    if (delay === undefined) {
      context.state.pending[nodeId] = false
      context.state.errors[nodeId] = detail
      return
    }

    context.state.pending[nodeId] = true
    context.state.errors[nodeId] = null
    const timer = setTimeout(() => {
      if (context.retryTimers.get(nodeId) === timer) {
        context.retryTimers.delete(nodeId)
      }
      if (!isCurrentRequest(context, nodeId, requestId)) return
      void fetchInContext(context, nodeId, {
        ...opts,
        retryAttempt: retryAttempt + 1,
      })
    }, delay)
    context.retryTimers.set(nodeId, timer)
  }

  async function fetchInContext(
    context: DataTableContext,
    nodeId: string,
    opts: FetchOpts = {},
  ): Promise<void> {
    if (context.released) return
    const retryAttempt = opts.retryAttempt ?? 0
    const current = stateFor(context, nodeId)
    const fallbackPageSize = paginatedSize(opts.pageSize ?? current.pageSize)
    const selectedIdentity = opts.captureLatest ? opts.resultIdentity ?? null : opts.resultIdentity ?? context.nodeIdentities.get(nodeId) ?? null
    const knownLegacy = !opts.captureLatest && !selectedIdentity && (
      context.nodeIdentities.has(nodeId)
      || context.state.projectionRequest?.sources.some(source => source.node_id === nodeId && !source.result_identity))
    let nextState: DataTablePageState = {
      page: opts.page ?? current.page,
      pageSize: browsingMode.value === 'continuous' && !knownLegacy ? CONTINUOUS_BLOCK_SIZE : fallbackPageSize,
      sortBy: opts.sortBy !== undefined ? opts.sortBy : current.sortBy,
      sortOrder: opts.sortOrder ?? current.sortOrder,
      filters: opts.filters ?? current.filters,
    }
    context.state.paginationState[nodeId] = nextState
    context.windows.get(nodeId)?.pause()
    context.nodeOptions.set(nodeId, { ...opts, captureLatest: false })

    clearRetry(context, nodeId)
    context.inflightControllers.get(nodeId)?.abort()
    const controller = new AbortController()
    context.inflightControllers.set(nodeId, controller)
    const requestId = (context.requestIds.get(nodeId) ?? 0) + 1
    context.requestIds.set(nodeId, requestId)

    context.state.loading[nodeId] = true
    context.state.errors[nodeId] = null
    try {
      const read = (identity: ResultArtifactIdentity | null) => api.post<NodeDataResponse>(
        `/api/v1/nodes/${encodeURIComponent(nodeId)}/data/query`,
        {
          page: nextState.page,
          page_size: nextState.pageSize,
          sort_by: nextState.sortBy,
          sort_order: nextState.sortOrder,
          filters: nextState.filters,
          tool_name: opts.toolName || null,
          workflow_name: opts.workflowName || null,
          result_identity: identity,
        },
        { signal: controller.signal },
      )
      let { data } = await read(selectedIdentity)
      for (let correction = 0; correction < 2 && browsingMode.value === 'continuous'; correction += 1) {
        if (!isCurrentRequest(context, nodeId, requestId)) return
        const size = data.source_identity ? CONTINUOUS_BLOCK_SIZE : fallbackPageSize
        if (size === nextState.pageSize) break
        nextState = { ...nextState, pageSize: size }
        opts = { ...opts, resultIdentity: data.source_identity ?? null }
        data = (await read(opts.resultIdentity ?? null)).data
      }
      if (isCurrentRequest(context, nodeId, requestId)) {
        context.state.paginationState[nodeId] = nextState
        if (opts.captureLatest || (context.nodeIdentities.has(nodeId) && JSON.stringify(context.nodeIdentities.get(nodeId) ?? null) !== JSON.stringify(data.source_identity ?? null))) retireInspection(context)
        resetWindow(context, nodeId)
        context.nodeIdentities.set(nodeId, data.source_identity ?? null)
        context.state.nodeDataCache[nodeId] = data
        if (browsingMode.value === 'continuous' && data.source_identity) windowFor(context, nodeId).seed(nextState.page, data)
        context.state.pending[nodeId] = false
      }
    } catch (exc: unknown) {
      if (!isCanceled(exc) && isCurrentRequest(context, nodeId, requestId)) {
        const message = errorMessage(exc)
        if (isRetryableResultConflict(exc)) {
          delete context.state.nodeDataCache[nodeId]
          scheduleNotReadyRetry(
            context,
            nodeId,
            opts,
            retryAttempt,
            requestId,
            message,
          )
        } else {
          context.state.pending[nodeId] = false
          context.state.errors[nodeId] = message
          if (!opts.captureLatest) delete context.state.nodeDataCache[nodeId]
        }
      }
    } finally {
      if (isCurrentRequest(context, nodeId, requestId)) {
        context.state.loading[nodeId] = false
        if (context.inflightControllers.get(nodeId) === controller) {
          context.inflightControllers.delete(nodeId)
        }
      }
    }
  }

  function fetchNodeData(nodeId: string, opts: FetchOpts = {}): Promise<void> {
    const context = activeContext(true)
    return context ? fetchInContext(context, nodeId, opts) : Promise.resolve()
  }

  function fetchCanvasNodeData(
    canvasId: CanvasId,
    nodeId: string,
    opts: FetchOpts = {},
  ): Promise<void> {
    const context = contextForCanvas(canvasId)
    return context ? fetchInContext(context, nodeId, opts) : Promise.resolve()
  }

  async function downloadCsv(
    nodeId: string,
    workflowName?: string | null,
    columns?: string[] | null,
  ): Promise<void> {
    const context = activeContext(false)
    const pageState = context ? stateFor(context, nodeId) : defaultPageState()
    try {
      const { data } = await api.post(
        `/api/v1/nodes/${encodeURIComponent(nodeId)}/data/csv`,
        {
          workflow_name: workflowName || null,
          columns: columns ?? null,
          result_identity: context?.nodeIdentities.get(nodeId) ?? context?.state.nodeDataCache[nodeId]?.source_identity ?? null,
          sort_by: pageState.sortBy,
          sort_order: pageState.sortOrder,
          filters: pageState.filters,
        },
        { responseType: 'blob' },
      )
      const href = URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href = href
      link.download = `${nodeId}.csv`
      link.style.display = 'none'
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(href)
    } catch (exc: unknown) {
      if (context) context.state.errors[nodeId] = errorMessage(exc)
    }
  }

  function clearContextCache(context: DataTableContext, nodeId?: string): void {
    const keys = nodeId
      ? [nodeId]
      : Array.from(new Set([
          ...Object.keys(context.state.nodeDataCache),
          ...Object.keys(context.state.paginationState),
          ...Object.keys(context.state.errors),
          ...Object.keys(context.state.loading),
          ...Object.keys(context.state.pending),
          ...context.inflightControllers.keys(),
          ...context.retryTimers.keys(),
          ...context.requestIds.keys(),
        ]))
    for (const key of keys) {
      invalidateRequest(context, key)
      resetWindow(context, key)
      context.nodeIdentities.delete(key)
      context.nodeOptions.delete(key)
      delete context.state.nodeDataCache[key]
      delete context.state.paginationState[key]
      delete context.state.errors[key]
      delete context.state.loading[key]
      delete context.state.pending[key]
    }
  }

  function clearCache(nodeId?: string): void {
    const context = activeContext(false)
    if (context) { retireInspection(context); clearContextCache(context, nodeId) }
  }

  function clearCanvasCache(canvasId: CanvasId, nodeId?: string): void {
    const context = existingCanvasContext(canvasId)
    if (context) { retireInspection(context); clearContextCache(context, nodeId) }
  }

  function setPageInContext(
    context: DataTableContext,
    nodeId: string,
    page: number,
    opts: { toolName?: string | null; workflowName?: string | null } = {},
  ): Promise<void> {
    return fetchInContext(context, nodeId, {
      ...stateFor(context, nodeId),
      page,
      ...opts,
      resultIdentity: context.state.nodeDataCache[nodeId]?.source_identity,
    })
  }

  function setPage(
    nodeId: string,
    page: number,
    opts: { toolName?: string | null; workflowName?: string | null } = {},
  ): Promise<void> {
    const context = activeContext(true)
    return context
      ? setPageInContext(context, nodeId, page, opts)
      : Promise.resolve()
  }

  function setPageSize(
    nodeId: string,
    pageSize: number,
    opts: { toolName?: string | null; workflowName?: string | null } = {},
  ): Promise<void> {
    const context = activeContext(true)
    return context
      ? fetchInContext(context, nodeId, {
          ...stateFor(context, nodeId),
          page: 0,
          pageSize,
          ...opts,
          resultIdentity: context.state.nodeDataCache[nodeId]?.source_identity,
        })
      : Promise.resolve()
  }

  function setSort(
    nodeId: string,
    sortBy: string | null,
    sortOrder: 'asc' | 'desc',
    opts: { toolName?: string | null; workflowName?: string | null } = {},
  ): Promise<void> {
    const context = activeContext(true)
    return context
      ? fetchInContext(context, nodeId, {
          ...stateFor(context, nodeId),
          page: 0,
          sortBy,
          sortOrder,
          ...opts,
          resultIdentity: context.state.nodeDataCache[nodeId]?.source_identity,
        })
      : Promise.resolve()
  }

  function setFilters(
    nodeId: string,
    filters: DataTableFilter[],
    opts: { toolName?: string | null; workflowName?: string | null } = {},
  ): Promise<void> {
    const context = activeContext(true)
    return context
      ? fetchInContext(context, nodeId, {
          ...stateFor(context, nodeId),
          page: 0,
          filters: [...filters],
          ...opts,
          resultIdentity: context.state.nodeDataCache[nodeId]?.source_identity,
        })
      : Promise.resolve()
  }

  function setPreferredPageSize(pageSize: number): void {
    preferredPageSize = pageSize
  }

  function getNodeData(nodeId: string): NodeDataResponse | undefined {
    return activeContext(false)?.state.nodeDataCache[nodeId]
  }

  function getCanvasNodeData(
    canvasId: CanvasId,
    nodeId: string,
  ): NodeDataResponse | undefined {
    return existingCanvasContext(canvasId)?.state.nodeDataCache[nodeId]
  }

  function getPageState(nodeId: string): DataTablePageState {
    return activeContext(false)?.state.paginationState[nodeId] ?? defaultPageState()
  }

  function getCanvasPageState(canvasId: CanvasId, nodeId: string): DataTablePageState {
    return existingCanvasContext(canvasId)?.state.paginationState[nodeId]
      ?? defaultPageState()
  }

  function isLoading(nodeId: string): boolean {
    return activeContext(false)?.state.loading[nodeId] === true
  }

  function isCanvasLoading(canvasId: CanvasId, nodeId: string): boolean {
    return existingCanvasContext(canvasId)?.state.loading[nodeId] === true
  }

  function getError(nodeId: string): string | null {
    return activeContext(false)?.state.errors[nodeId] ?? null
  }

  function getCanvasError(canvasId: CanvasId, nodeId: string): string | null {
    return existingCanvasContext(canvasId)?.state.errors[nodeId] ?? null
  }

  function isPending(nodeId: string): boolean {
    return activeContext(false)?.state.pending[nodeId] === true
  }

  function isCanvasPending(canvasId: CanvasId, nodeId: string): boolean {
    return existingCanvasContext(canvasId)?.state.pending[nodeId] === true
  }

  function releaseCanvas(canvasId: CanvasId): void {
    releasedCanvasIds.add(canvasId)
    const context = existingCanvasContext(canvasId)
    if (!context) return
    context.released = true
    invalidateProjection(context)
    clearContextCache(context)
    context.requestIds.clear()
    for (const window of context.windows.values()) window.reset()
    context.windows.clear()
    canvasContexts.delete(canvasId)
  }

  function isContinuous(nodeId?: string): boolean {
    if (browsingMode.value !== 'continuous') return false
    const context = activeContext(false)
    if (!context) return false
    return nodeId
      ? Boolean(context.nodeIdentities.get(nodeId))
      : context.state.projection?.mode === 'merged' && context.state.projection.sources.every(source => source.result_identity)
  }

  function tableEntries(nodeId?: string): Array<{ index: number; row: Record<string, any> }> {
    const context = activeContext(false)
    if (!context) return []
    void context.state.windowRevision
    const continuous = isContinuous(nodeId)
    const key = nodeId ?? 'projection'
    const blocks = continuous ? [...(context.windows.get(key)?.blocks.entries() ?? [])] : []
    if (!continuous) {
      const data = nodeId ? context.state.nodeDataCache[nodeId] : context.state.projection
      if (data && (!('mode' in data) || data.mode === 'merged')) blocks.push([0, data])
    }
    return blocks.flatMap<{ index: number; row: Record<string, any> }>(([page, data]) => {
      const start = continuous ? page * CONTINUOUS_BLOCK_SIZE : 0
      if ('mode' in data) {
        return data.rows.map((row, i) => ({ index: start + i,
          row: { ...row.values, __index: row.index, __sourceRows: row.source_rows } }))
      }
      return data.rows.map((row, i) => ({ index: start + i,
        row: { ...row, __absoluteRow: data.absolute_rows[i] } }))
    }).sort((a, b) => a.index - b.index)
  }

  function continuousErrors(nodeId?: string): string[] {
    const context = activeContext(false)
    if (!context) return []
    void context.state.windowRevision
    return [...(context.windows.get(nodeId ?? 'projection')?.errors.values() ?? [])]
  }

  function retryContinuous(nodeId?: string): void {
    activeContext(false)?.windows.get(nodeId ?? 'projection')?.retry()
  }

  function loadTableRange(start: number, end: number, nodeId?: string): void {
    const context = activeContext(false)
    if (!context || !isContinuous(nodeId)) return
    if (nodeId ? context.state.loading[nodeId] : context.state.projectionLoading) return
    const key = nodeId ?? 'projection'
    const window = context.windows.get(key)
    if (!window) return
    const metadata = nodeId ? context.state.nodeDataCache[nodeId] : context.state.projection
    if (!metadata || ('mode' in metadata && metadata.mode !== 'merged')) return
    const capturedInspection = context.state.inspectionRevision
    const request = context.state.projectionRequest
    const pageState = nodeId ? stateFor(context, nodeId) : context.state.projectionPage
    const options = nodeId ? context.nodeOptions.get(nodeId) : null
    const identity = nodeId ? context.nodeIdentities.get(nodeId) : null
    const queryToken = nodeId ? context.requestIds.get(nodeId) : context.projectionRequestId
    window.range(start, end, metadata.total_rows, async (page, signal) => {
      const body = { page, page_size: CONTINUOUS_BLOCK_SIZE, sort_by: pageState.sortBy,
        sort_order: pageState.sortOrder, filters: pageState.filters }
      const data = nodeId
        ? await readTableBlock<NodeDataResponse>(`/api/v1/nodes/${encodeURIComponent(nodeId)}/data/query`, {
          ...body, tool_name: options?.toolName ?? null, workflow_name: options?.workflowName ?? null,
          result_identity: identity,
        }, signal)
        : await readTableBlock<MergedDataTableResponse>('/api/v1/data-table/query', { ...request, ...body }, signal)
      if (context.released || context.state.inspectionRevision !== capturedInspection
        || (nodeId ? context.requestIds.get(nodeId) : context.projectionRequestId) !== queryToken) return null
      if ('mode' in data) {
        if (data.mode !== 'merged' || JSON.stringify(data.sources.map(source => source.result_identity))
          !== JSON.stringify(request?.sources.map(source => source.result_identity))) throw new Error('The output snapshot changed. Refresh the table.')
      } else if (JSON.stringify(data.source_identity) !== JSON.stringify(identity)) throw new Error('The output snapshot changed. Refresh the table.')
      return data
    })
  }

  return {
    nodeDataCache,
    inspectionKey,
    browsingMode,
    setBrowsingMode,
    isContinuous,
    tableEntries,
    continuousErrors,
    retryContinuous,
    loadTableRange,
    paginationState,
    loading,
    errors,
    pending,
    upstreamDepth,
    projection,
    projectionLoading,
    projectionError,
    projectionPage,
    setUpstreamDepth,
    fetchProjection,
    clearProjection,
    setProjectionPage,
    setProjectionSort,
    setProjectionFilters,
    downloadProjectionCsv,
    registerCanvas,
    fetchNodeData,
    fetchCanvasNodeData,
    downloadCsv,
    clearCache,
    clearCanvasCache,
    setPage,
    setPageSize,
    setSort,
    setFilters,
    setPreferredPageSize,
    getNodeData,
    getCanvasNodeData,
    getPageState,
    getCanvasPageState,
    isLoading,
    isCanvasLoading,
    getError,
    getCanvasError,
    isPending,
    isCanvasPending,
    releaseCanvas,
  }
})
