import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import { useErrorReporting } from '@/composables/useErrorReporting'
import { useLoggerStore } from '@/stores/logger'
import type {
  GraphState,
  GraphValidationError,
  NodeStatus,
} from '@/api/types'

// These mirror bioimageflow_server.models.execution but aren't auto-generated
// because the /execution/status endpoint is typed as a raw dict.
export interface ProgressInfo {
  node_id: string
  row: number
  total_rows: number
}

export interface ExecutionResult {
  success: boolean
  errors: Array<Record<string, unknown>>
  node_statuses: Record<string, NodeStatus>
}

export interface ExecutionStatus {
  state: 'running' | 'idle'
  last_result: ExecutionResult | null
  progress: ProgressInfo | null
}

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
  response?: {
    status?: number
    data?: { detail?: string; error?: string; errors?: GraphValidationError[] }
  }
  message?: string
}

function messageFromError(err: RunError): string {
  return err.response?.data?.detail ?? err.message ?? String(err)
}

function stringifyExecutionError(err: Record<string, unknown>): string {
  const detail = typeof err.detail === 'string' ? err.detail : null
  const error = typeof err.error === 'string' ? err.error : null
  const type = typeof err.type === 'string' ? err.type : null
  if (detail && type) return `${type}: ${detail}`
  return detail ?? error ?? JSON.stringify(err)
}

function stringifyExecutionErrorWithTraceback(err: Record<string, unknown>): string {
  const summary = stringifyExecutionError(err)
  const tb = typeof err.traceback === 'string' ? err.traceback : null
  return tb ? `${summary}\n${tb}` : summary
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

  async function run(
    graph: GraphState,
    nodes?: string[],
    workflowName?: string | null,
  ) {
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
      await api.post('/api/v1/execution/run', {
        graph,
        nodes,
        workflow_name: workflowName ?? null,
      })
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
      error.value = messageFromError(err)
      useLoggerStore().addEntry({
        level: 'ERROR',
        message: error.value,
        nodeId: null,
        timestamp: Date.now() / 1000,
      })
      throw e
    }
  }

  async function stop() {
    await api.post('/api/v1/execution/stop')
  }

  async function clear(
    graph: GraphState,
    nodeIds: string[],
    workflowName?: string | null,
  ) {
    const { data } = await api.post<ClearResponse>(
      '/api/v1/execution/clear',
      { graph, nodes: nodeIds, workflow_name: workflowName ?? null },
    )
    if (data?.node_statuses) {
      nodeStatuses.value = { ...nodeStatuses.value, ...data.node_statuses }
    }
    useLoggerStore().addEntry({
      level: 'INFO',
      message: `Execution cache cleared for ${nodeIds.length} node${nodeIds.length === 1 ? '' : 's'}`,
      nodeId: null,
      timestamp: Date.now() / 1000,
    })
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

    if (!payload.success) {
      _reportFailure(payload)
    }
  }

  function _reportFailure(payload: ExecutionResult): void {
    const failedEntries = Object.entries(payload.node_statuses ?? {}).filter(
      ([, s]) => s.status === 'failed',
    )

    let detail: string
    let fullDetail: string | undefined
    let nodeId: string | undefined
    if (failedEntries.length > 0) {
      const [firstId, firstStatus] = failedEntries[0]!
      nodeId = firstId
      const firstMsg = `${firstId}: ${firstStatus.error ?? 'unknown error'}`
      detail =
        failedEntries.length === 1
          ? firstMsg
          : `${failedEntries.length} nodes failed; first: ${firstMsg}`
      fullDetail = failedEntries
        .map(([id, status]) => [
          `${id}: ${status.error ?? 'unknown error'}`,
          status.traceback ?? null,
        ].filter((part): part is string => Boolean(part)).join('\n'))
        .join('\n\n')
    } else if (payload.errors?.length) {
      detail = stringifyExecutionError(payload.errors[0]!)
      fullDetail = payload.errors.map(stringifyExecutionErrorWithTraceback).join('\n\n')
    } else {
      detail = 'Execution failed'
    }

    try {
      const { reportError } = useErrorReporting()
      reportError({
        kind: 'execution_failed',
        detail,
        ...(fullDetail ? { fullDetail } : {}),
        ...(nodeId ? { nodeId } : {}),
        logToLogger: false,
      })
    } catch (e) {
      // Best-effort: in test contexts the composable may not have access
      // to a Toast provider. Surface unexpected failures so real bugs in
      // the reporting path don't go unnoticed.
      console.warn('[execution] failed to report execution_failed:', e)
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
