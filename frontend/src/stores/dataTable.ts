import { computed, reactive } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { NodeDataResponse } from '@/api/types'

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

const NOT_READY_RETRY_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 15_000]

export const useDataTableStore = defineStore('dataTable', () => {
  const nodeDataCache = reactive<Record<string, NodeDataResponse>>({})
  const paginationState = reactive<Record<string, DataTablePageState>>({})
  const loading = reactive<Record<string, boolean>>({})
  const errors = reactive<Record<string, string | null>>({})
  const pending = reactive<Record<string, boolean>>({})

  const inflightController = new Map<string, AbortController>()
  const requestIds = new Map<string, number>()
  const retryTimers = new Map<string, ReturnType<typeof setTimeout>>()

  function stateFor(nodeId: string): DataTablePageState {
    if (!paginationState[nodeId]) {
      paginationState[nodeId] = {
        page: 0,
        pageSize: 50,
        sortBy: null,
        sortOrder: 'asc',
      }
    }
    return paginationState[nodeId]
  }

  function clearRetry(nodeId: string) {
    const timer = retryTimers.get(nodeId)
    if (timer !== undefined) {
      clearTimeout(timer)
      retryTimers.delete(nodeId)
    }
  }

  function scheduleNotReadyRetry(
    nodeId: string,
    opts: FetchOpts,
    retryAttempt: number,
    requestId: number,
    detail: string,
  ) {
    clearRetry(nodeId)
    const delay = NOT_READY_RETRY_DELAYS_MS[retryAttempt]
    if (delay === undefined) {
      pending[nodeId] = false
      errors[nodeId] = detail
      return
    }

    pending[nodeId] = true
    errors[nodeId] = null
    retryTimers.set(
      nodeId,
      setTimeout(() => {
        retryTimers.delete(nodeId)
        if (requestIds.get(nodeId) !== requestId) return
        void fetchNodeData(nodeId, {
          ...opts,
          retryAttempt: retryAttempt + 1,
        })
      }, delay),
    )
  }

  async function fetchNodeData(nodeId: string, opts: FetchOpts = {}) {
    const retryAttempt = opts.retryAttempt ?? 0
    const current = stateFor(nodeId)
    const nextState: DataTablePageState = {
      page: opts.page ?? current.page,
      pageSize: opts.pageSize ?? current.pageSize,
      sortBy: opts.sortBy ?? current.sortBy,
      sortOrder: opts.sortOrder ?? current.sortOrder,
    }
    paginationState[nodeId] = nextState

    clearRetry(nodeId)
    inflightController.get(nodeId)?.abort()
    const controller = new AbortController()
    inflightController.set(nodeId, controller)
    const requestId = (requestIds.get(nodeId) ?? 0) + 1
    requestIds.set(nodeId, requestId)

    loading[nodeId] = true
    errors[nodeId] = null
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
      if (requestIds.get(nodeId) === requestId) {
        nodeDataCache[nodeId] = data
        pending[nodeId] = false
      }
    } catch (exc: unknown) {
      const maybeCanceled = exc as { name?: string; code?: string }
      if (maybeCanceled.name !== 'CanceledError' && maybeCanceled.code !== 'ERR_CANCELED') {
        const message = errorMessage(exc)
        if (errorStatus(exc) === 409 && requestIds.get(nodeId) === requestId) {
          delete nodeDataCache[nodeId]
          scheduleNotReadyRetry(nodeId, opts, retryAttempt, requestId, message)
        } else {
          pending[nodeId] = false
          errors[nodeId] = message
          delete nodeDataCache[nodeId]
        }
      }
    } finally {
      if (requestIds.get(nodeId) === requestId) {
        loading[nodeId] = false
        if (inflightController.get(nodeId) === controller) {
          inflightController.delete(nodeId)
        }
      }
    }
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

  function clearCache(nodeId?: string) {
    const keys = nodeId ? [nodeId] : Object.keys(nodeDataCache)
    for (const key of keys) {
      delete nodeDataCache[key]
      delete paginationState[key]
      delete errors[key]
      delete loading[key]
      delete pending[key]
      clearRetry(key)
      inflightController.get(key)?.abort()
      inflightController.delete(key)
    }
  }

  function setPage(
    nodeId: string,
    page: number,
    opts: { toolName?: string | null; workflowName?: string | null } = {},
  ) {
    return fetchNodeData(nodeId, {
      ...stateFor(nodeId),
      page,
      toolName: opts.toolName,
      workflowName: opts.workflowName,
    })
  }

  function setPageSize(
    nodeId: string,
    pageSize: number,
    opts: { toolName?: string | null; workflowName?: string | null } = {},
  ) {
    return fetchNodeData(nodeId, {
      ...stateFor(nodeId),
      page: 0,
      pageSize,
      toolName: opts.toolName,
      workflowName: opts.workflowName,
    })
  }

  function setSort(
    nodeId: string,
    sortBy: string | null,
    sortOrder: 'asc' | 'desc',
    opts: { toolName?: string | null; workflowName?: string | null } = {},
  ) {
    return fetchNodeData(nodeId, {
      ...stateFor(nodeId),
      sortBy,
      sortOrder,
      toolName: opts.toolName,
      workflowName: opts.workflowName,
    })
  }

  const getNodeData = computed(() => (nodeId: string) => nodeDataCache[nodeId])
  const isLoading = computed(() => (nodeId: string) => loading[nodeId] === true)
  const getError = computed(() => (nodeId: string) => errors[nodeId] ?? null)
  const isPending = computed(() => (nodeId: string) => pending[nodeId] === true)

  return {
    nodeDataCache,
    paginationState,
    loading,
    errors,
    pending,
    fetchNodeData,
    downloadCsv,
    clearCache,
    setPage,
    setPageSize,
    setSort,
    getNodeData,
    isLoading,
    getError,
    isPending,
  }
})
