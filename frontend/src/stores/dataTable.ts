import { computed, reactive, shallowReactive } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { NodeDataResponse } from '@/api/types'
import {
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'

export interface DataTablePageState {
  page: number
  pageSize: number
  sortBy: string | null
  sortOrder: 'asc' | 'desc'
}

export interface DataTableSourceRequest {
  node_id: string
  role: 'anchor' | 'context'
  label: string
  tool_name?: string | null
  columns?: string[] | null
  column_aliases: Record<string, string>
}

export interface ConsolidatedDataTableColumn {
  id: string
  label: string
  type: string
  source_node_id: string
  source_column: string
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
  retryAttempt?: number
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
}

const EMPTY_NODE_DATA = Object.freeze({}) as Record<string, NodeDataResponse>
const EMPTY_PAGINATION = Object.freeze({}) as Record<string, DataTablePageState>
const EMPTY_FLAGS = Object.freeze({}) as Record<string, boolean>
const EMPTY_ERRORS = Object.freeze({}) as Record<string, string | null>

function defaultPageState(): DataTablePageState {
  return {
    page: 0,
    pageSize: 50,
    sortBy: null,
    sortOrder: 'asc',
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
    }) as DataTableState,
    inflightControllers: new Map(),
    requestIds: new Map(),
    retryTimers: new Map(),
    projectionController: null,
    projectionRetryTimer: null,
    projectionRequestId: 0,
    released: false,
  }
}

function errorMessage(exc: unknown): string {
  if (typeof exc === 'object' && exc !== null && 'response' in exc) {
    const response = (exc as { response?: { data?: { detail?: string } } }).response
    if (response?.data?.detail) return response.data.detail
  }
  return exc instanceof Error ? exc.message : String(exc)
}

function errorStatus(exc: unknown): number | null {
  if (typeof exc === 'object' && exc !== null && 'response' in exc) {
    const response = (exc as { response?: { status?: number } }).response
    return response?.status ?? null
  }
  return null
}

function isCanceled(exc: unknown): boolean {
  const maybeCanceled = exc as { name?: string; code?: string }
  return maybeCanceled.name === 'CanceledError' || maybeCanceled.code === 'ERR_CANCELED'
}

const NOT_READY_RETRY_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 15_000]

export const useDataTableStore = defineStore('dataTable', () => {
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

  async function fetchProjectionInContext(
    context: DataTableContext,
    request: DataTableProjectionRequest,
    pageState: DataTablePageState = context.state.projectionPage,
    retryAttempt = 0,
  ): Promise<void> {
    if (context.released) return
    invalidateProjection(context)
    const controller = new AbortController()
    context.projectionController = controller
    const requestId = context.projectionRequestId
    context.state.projectionRequest = request
    context.state.projectionPage = { ...pageState }
    context.state.projectionLoading = true
    context.state.projectionError = null
    let retryScheduled = false
    try {
      const { data } = await api.post<DataTableProjectionResponse>(
        '/api/v1/data-table/query',
        {
          ...request,
          page: pageState.page,
          page_size: pageState.pageSize,
          sort_by: pageState.sortBy,
          sort_order: pageState.sortOrder,
        },
        { signal: controller.signal },
      )
      if (!context.released && context.projectionRequestId === requestId) {
        context.state.projection = data
      }
    } catch (exc: unknown) {
      if (!isCanceled(exc) && !context.released && context.projectionRequestId === requestId) {
        if (errorStatus(exc) === 409 && retryAttempt < NOT_READY_RETRY_DELAYS_MS.length) {
          retryScheduled = true
          const timer = setTimeout(() => {
            if (context.projectionRetryTimer === timer) context.projectionRetryTimer = null
            if (!context.released && context.projectionRequestId === requestId) {
              void fetchProjectionInContext(context, request, pageState, retryAttempt + 1)
            }
          }, NOT_READY_RETRY_DELAYS_MS[retryAttempt])
          context.projectionRetryTimer = timer
        } else {
          context.state.projection = null
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

  function fetchProjection(request: DataTableProjectionRequest): Promise<void> {
    const context = activeContext(true)
    if (!context) return Promise.resolve()
    return fetchProjectionInContext(context, request, defaultPageState())
  }

  function clearProjection(): void {
    const context = activeContext(false)
    if (!context) return
    invalidateProjection(context)
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
      pageSize: pageSize ?? context.state.projectionPage.pageSize,
    })
  }

  function setProjectionSort(sortBy: string, sortOrder: 'asc' | 'desc'): Promise<void> {
    const context = activeContext(true)
    if (!context?.state.projectionRequest) return Promise.resolve()
    return fetchProjectionInContext(context, context.state.projectionRequest, {
      ...context.state.projectionPage,
      page: 0,
      sortBy,
      sortOrder,
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
    const nextState: DataTablePageState = {
      page: opts.page ?? current.page,
      pageSize: opts.pageSize ?? current.pageSize,
      sortBy: opts.sortBy ?? current.sortBy,
      sortOrder: opts.sortOrder ?? current.sortOrder,
    }
    context.state.paginationState[nodeId] = nextState

    clearRetry(context, nodeId)
    context.inflightControllers.get(nodeId)?.abort()
    const controller = new AbortController()
    context.inflightControllers.set(nodeId, controller)
    const requestId = (context.requestIds.get(nodeId) ?? 0) + 1
    context.requestIds.set(nodeId, requestId)

    context.state.loading[nodeId] = true
    context.state.errors[nodeId] = null
    try {
      const params: Record<string, string | number> = {
        page: nextState.page,
        page_size: nextState.pageSize,
        sort_order: nextState.sortOrder,
      }
      if (nextState.sortBy) params.sort_by = nextState.sortBy
      if (opts.toolName && opts.toolName.trim() !== '') {
        params.tool_name = opts.toolName
      }
      if (opts.workflowName && opts.workflowName.trim() !== '') {
        params.workflow_name = opts.workflowName
      }
      const { data } = await api.get<NodeDataResponse>(
        `/api/v1/nodes/${encodeURIComponent(nodeId)}/data`,
        { params, signal: controller.signal },
      )
      if (isCurrentRequest(context, nodeId, requestId)) {
        context.state.nodeDataCache[nodeId] = data
        context.state.pending[nodeId] = false
      }
    } catch (exc: unknown) {
      if (!isCanceled(exc) && isCurrentRequest(context, nodeId, requestId)) {
        const message = errorMessage(exc)
        if (errorStatus(exc) === 409) {
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
          delete context.state.nodeDataCache[nodeId]
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

  function downloadCsv(
    nodeId: string,
    workflowName?: string | null,
    columns?: string[] | null,
  ) {
    const link = document.createElement('a')
    const params = new URLSearchParams()
    if (workflowName && workflowName.trim() !== '') {
      params.set('workflow_name', workflowName)
    }
    for (const column of columns ?? []) {
      params.append('columns', column)
    }
    const query = params.toString()
    link.href =
      `/api/v1/nodes/${encodeURIComponent(nodeId)}/data/csv` +
      (query ? `?${query}` : '')
    link.download = `${nodeId}.csv`
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    link.remove()
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
      delete context.state.nodeDataCache[key]
      delete context.state.paginationState[key]
      delete context.state.errors[key]
      delete context.state.loading[key]
      delete context.state.pending[key]
    }
  }

  function clearCache(nodeId?: string): void {
    const context = activeContext(false)
    if (context) clearContextCache(context, nodeId)
  }

  function clearCanvasCache(canvasId: CanvasId, nodeId?: string): void {
    const context = existingCanvasContext(canvasId)
    if (context) clearContextCache(context, nodeId)
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
          sortBy,
          sortOrder,
          ...opts,
        })
      : Promise.resolve()
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
    canvasContexts.delete(canvasId)
  }

  return {
    nodeDataCache,
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
