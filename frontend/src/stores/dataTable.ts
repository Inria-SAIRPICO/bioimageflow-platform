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
}

interface DataTableContext {
  readonly state: DataTableState
  readonly inflightControllers: Map<string, AbortController>
  readonly requestIds: Map<string, number>
  readonly retryTimers: Map<string, ReturnType<typeof setTimeout>>
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
    }) as DataTableState,
    inflightControllers: new Map(),
    requestIds: new Map(),
    retryTimers: new Map(),
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
  const legacyContext = createContext()
  const canvasContexts = shallowReactive(new Map<CanvasId, DataTableContext>())

  function contextForCanvas(canvasId: CanvasId): DataTableContext {
    const existing = canvasContexts.get(canvasId)
    if (existing) return existing
    const created = createContext()
    canvasContexts.set(canvasId, created)
    return created
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
    return canvasSessionRegistry.sessionCount.value === 0
      ? legacyContext
      : null
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
    context.retryTimers.set(
      nodeId,
      setTimeout(() => {
        context.retryTimers.delete(nodeId)
        if (!isCurrentRequest(context, nodeId, requestId)) return
        void fetchInContext(context, nodeId, {
          ...opts,
          retryAttempt: retryAttempt + 1,
        })
      }, delay),
    )
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
    return fetchInContext(contextForCanvas(canvasId), nodeId, opts)
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
    const context = existingCanvasContext(canvasId)
    if (!context) return
    context.released = true
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
