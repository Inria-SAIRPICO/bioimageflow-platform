import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type {
  ExecutionResult,
  ExecutionStatus,
  GraphState,
  GraphValidationError,
  NodeStatus,
  ProgressInfo,
} from '@/api/types'

interface NodeStateMessage {
  node_id: string
  status: NodeStatus['status']
  cached: boolean
  error?: string | null
  traceback?: string | null
}

interface ExecutionStatusResponse extends ExecutionStatus {
  node_statuses?: Record<string, NodeStatus>
}

interface ClearResponse {
  node_statuses: Record<string, NodeStatus>
}

interface RunError {
  status?: number
  response?: { status?: number; data?: { errors?: GraphValidationError[] } }
  message?: string
}

export const useExecutionStore = defineStore('execution', () => {
  const state = ref<'running' | 'idle'>('idle')
  const lastResult = ref<ExecutionResult | null>(null)
  const progress = ref<ProgressInfo | null>(null)
  const nodeStatuses = ref<Record<string, NodeStatus>>({})
  const error = ref<string | null>(null)
  const isConflict = ref(false)
  const validationErrors = ref<GraphValidationError[]>([])

  const isRunning = computed(() => state.value === 'running')

  async function fetchStatus() {
    try {
      const { data } = await api.get<ExecutionStatusResponse>(
        '/api/v1/execution/status',
      )
      state.value = data.state
      lastResult.value = data.last_result
      progress.value = data.progress
      if (data.node_statuses) {
        nodeStatuses.value = { ...nodeStatuses.value, ...data.node_statuses }
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  async function run(graph: GraphState, nodes?: string[]) {
    if (state.value === 'running') {
      throw new Error('already running')
    }
    error.value = null
    isConflict.value = false
    validationErrors.value = []
    lastResult.value = null
    progress.value = null
    nodeStatuses.value = {}
    try {
      await api.post('/api/v1/execution/run', { graph, nodes })
      state.value = 'running'
    } catch (e: unknown) {
      state.value = 'idle'
      const err = e as RunError
      const status = err.response?.status ?? err.status
      if (status === 409) {
        isConflict.value = true
      } else if (status === 422) {
        validationErrors.value = err.response?.data?.errors ?? []
      }
      error.value = e instanceof Error ? e.message : String(e)
      throw e
    }
  }

  async function stop() {
    await api.post('/api/v1/execution/stop')
  }

  async function clear(graph: GraphState, nodeIds: string[]) {
    const { data } = await api.post<ClearResponse>(
      '/api/v1/execution/clear',
      { graph, nodes: nodeIds },
    )
    if (data?.node_statuses) {
      nodeStatuses.value = { ...nodeStatuses.value, ...data.node_statuses }
    }
    return data
  }

  function applyProgress(p: ProgressInfo) {
    progress.value = p
  }

  function applyNodeState(msg: NodeStateMessage) {
    nodeStatuses.value = {
      ...nodeStatuses.value,
      [msg.node_id]: {
        node_id: msg.node_id,
        status: msg.status,
        cached: msg.cached,
        error: msg.error ?? null,
        traceback: msg.traceback ?? null,
      },
    }
  }

  function applyExecutionComplete(payload: ExecutionResult) {
    state.value = 'idle'
    lastResult.value = payload
    progress.value = null
    if (payload.node_statuses) {
      nodeStatuses.value = { ...nodeStatuses.value, ...payload.node_statuses }
    }
  }

  return {
    state,
    lastResult,
    progress,
    nodeStatuses,
    error,
    isConflict,
    validationErrors,
    isRunning,
    fetchStatus,
    run,
    stop,
    clear,
    applyProgress,
    applyNodeState,
    applyExecutionComplete,
  }
})
