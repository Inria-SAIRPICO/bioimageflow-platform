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
  page?: number
  pageSize?: number
  sortBy?: string | null
  sortOrder?: 'asc' | 'desc'
}

function errorMessage(exc: unknown): string {
  if (typeof exc === 'object' && exc !== null && 'response' in exc) {
    const response = (exc as { response?: { data?: { detail?: string } } }).response
    if (response?.data?.detail) return response.data.detail
  }
  return exc instanceof Error ? exc.message : String(exc)
}

export const useDataTableStore = defineStore('dataTable', () => {
  const nodeDataCache = reactive<Record<string, NodeDataResponse>>({})
  const paginationState = reactive<Record<string, DataTablePageState>>({})
  const loading = reactive<Record<string, boolean>>({})
  const errors = reactive<Record<string, string | null>>({})

  const inflightController = new Map<string, AbortController>()
  const requestIds = new Map<string, number>()

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

  async function fetchNodeData(nodeId: string, opts: FetchOpts = {}) {
    const current = stateFor(nodeId)
    const nextState: DataTablePageState = {
      page: opts.page ?? current.page,
      pageSize: opts.pageSize ?? current.pageSize,
      sortBy: opts.sortBy ?? current.sortBy,
      sortOrder: opts.sortOrder ?? current.sortOrder,
    }
    paginationState[nodeId] = nextState

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
      const { data } = await api.get<NodeDataResponse>(
        `/api/v1/nodes/${encodeURIComponent(nodeId)}/data`,
        { params, signal: controller.signal },
      )
      if (requestIds.get(nodeId) === requestId) {
        nodeDataCache[nodeId] = data
      }
    } catch (exc: unknown) {
      const maybeCanceled = exc as { name?: string; code?: string }
      if (maybeCanceled.name !== 'CanceledError' && maybeCanceled.code !== 'ERR_CANCELED') {
        errors[nodeId] = errorMessage(exc)
        delete nodeDataCache[nodeId]
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

  function downloadCsv(nodeId: string) {
    const link = document.createElement('a')
    link.href = `/api/v1/nodes/${encodeURIComponent(nodeId)}/data/csv`
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
      inflightController.get(key)?.abort()
      inflightController.delete(key)
    }
  }

  function setPage(nodeId: string, page: number, opts: { toolName?: string | null } = {}) {
    return fetchNodeData(nodeId, { ...stateFor(nodeId), page, toolName: opts.toolName })
  }

  function setPageSize(
    nodeId: string,
    pageSize: number,
    opts: { toolName?: string | null } = {},
  ) {
    return fetchNodeData(nodeId, { ...stateFor(nodeId), page: 0, pageSize, toolName: opts.toolName })
  }

  function setSort(
    nodeId: string,
    sortBy: string | null,
    sortOrder: 'asc' | 'desc',
    opts: { toolName?: string | null } = {},
  ) {
    return fetchNodeData(nodeId, { ...stateFor(nodeId), sortBy, sortOrder, toolName: opts.toolName })
  }

  const getNodeData = computed(() => (nodeId: string) => nodeDataCache[nodeId])
  const isLoading = computed(() => (nodeId: string) => loading[nodeId] === true)
  const getError = computed(() => (nodeId: string) => errors[nodeId] ?? null)

  return {
    nodeDataCache,
    paginationState,
    loading,
    errors,
    fetchNodeData,
    downloadCsv,
    clearCache,
    setPage,
    setPageSize,
    setSort,
    getNodeData,
    isLoading,
    getError,
  }
})
