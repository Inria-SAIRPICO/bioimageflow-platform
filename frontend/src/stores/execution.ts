import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import { useErrorReporting } from '@/composables/useErrorReporting'
import { useLoggerStore } from '@/stores/logger'
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
  result_key?: string | null
  record_id?: string | null
}

interface ExecutionStatusResponse extends ExecutionStatus {
  node_statuses?: Record<string, NodeStatus>
}

interface ExecutionStatusSnapshot extends ExecutionStatus {
  node_statuses?: Record<string, NodeStatus>
}

interface ClearResponse {
  node_statuses: Record<string, NodeStatus>
}

export interface EnvironmentRecoveryAction {
  kind: 'delete_environment'
  envName: string
  path?: string
  existingHash?: string
  requestedHash?: string
  nodeId?: string
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

function failedNodeIdFromResult(result: ExecutionResult): string | undefined {
  const failed = Object.values(result.node_statuses ?? {}).find(
    (status) => status.status === 'failed',
  )
  return failed?.node_id
}

function stringField(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined
}

function recoveryActionKey(action: EnvironmentRecoveryAction): string {
  return [
    action.kind,
    action.envName,
    action.path ?? '',
    action.existingHash ?? '',
    action.requestedHash ?? '',
  ].join('\n')
}

function extractEnvironmentRecoveryAction(
  result: ExecutionResult | null,
): EnvironmentRecoveryAction | null {
  if (!result || result.success) return null
  for (const error of result.errors ?? []) {
    const recovery = error.recovery_action
    if (typeof recovery !== 'object' || recovery === null) continue
    const action = recovery as Record<string, unknown>
    if (action.kind !== 'delete_environment') continue
    const envName = stringField(action.env_name)
    if (!envName) continue
    return {
      kind: 'delete_environment',
      envName,
      ...(stringField(action.path) ? { path: stringField(action.path) } : {}),
      ...(stringField(action.existing_hash)
        ? { existingHash: stringField(action.existing_hash) }
        : {}),
      ...(stringField(action.requested_hash)
        ? { requestedHash: stringField(action.requested_hash) }
        : {}),
      ...(stringField(action.node_id)
        ? { nodeId: stringField(action.node_id) }
        : failedNodeIdFromResult(result)
          ? { nodeId: failedNodeIdFromResult(result) }
          : {}),
    }
  }
  return null
}

function hasExistingFailureLog(
  nodeId: string | undefined,
  detail: string,
  fullDetail: string | undefined,
): boolean {
  const logger = useLoggerStore()
  const errorText = detail.includes(': ') ? detail.split(': ').slice(1).join(': ') : detail
  const traceback = fullDetail?.split('\n').slice(1).join('\n') ?? ''
  return logger.entries.some((entry) => {
    if (entry.level !== 'ERROR') return false
    if ((nodeId ?? null) !== entry.nodeId) return false
    if (!entry.message.includes(errorText)) return false
    return !traceback || entry.message.includes(traceback)
  })
}

export const useExecutionStore = defineStore('execution', () => {
  const state = ref<'running' | 'idle'>('idle')
  const lastResult = ref<ExecutionResult | null>(null)
  const progress = ref<ProgressInfo | null>(null)
  const nodeStatuses = ref<Record<string, NodeStatus>>({})
  const error = ref<string | null>(null)
  const isConflict = ref(false)
  const validationErrors = ref<GraphValidationError[]>([])
  const environmentRecoveryAction = ref<EnvironmentRecoveryAction | null>(null)
  const dismissedEnvironmentRecoveryKey = ref<string | null>(null)

  const isRunning = computed(() => state.value === 'running')
  const isEnvironmentRecoveryDialogVisible = computed(() => {
    const action = environmentRecoveryAction.value
    if (action === null) return false
    return dismissedEnvironmentRecoveryKey.value !== recoveryActionKey(action)
  })

  function updateEnvironmentRecovery(result: ExecutionResult | null): void {
    environmentRecoveryAction.value = extractEnvironmentRecoveryAction(result)
  }

  function clearEnvironmentRecovery(): void {
    environmentRecoveryAction.value = null
    dismissedEnvironmentRecoveryKey.value = null
  }

  function dismissEnvironmentRecovery(): void {
    const action = environmentRecoveryAction.value
    if (action === null) return
    dismissedEnvironmentRecoveryKey.value = recoveryActionKey(action)
  }

  async function fetchStatus() {
    try {
      const { data } = await api.get<ExecutionStatusResponse>(
        '/api/v1/execution/status',
      )
      state.value = data.state
      lastResult.value = data.last_result
      updateEnvironmentRecovery(data.last_result)
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
    clearEnvironmentRecovery()
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
    workflowName: string,
  ) {
    const { data } = await api.post<ClearResponse>(
      '/api/v1/execution/clear',
      { graph, nodes: nodeIds, workflow_name: workflowName },
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
    state.value = 'running'
    progress.value = p
  }

  function applyNodeState(msg: NodeStateMessage) {
    if (msg.status === 'running') {
      state.value = 'running'
    }
    nodeStatuses.value = {
      ...nodeStatuses.value,
      [msg.node_id]: {
        node_id: msg.node_id,
        status: msg.status,
        cached: msg.cached,
        error: msg.error ?? null,
        traceback: msg.traceback ?? null,
        ...(msg.result_key !== undefined ? { result_key: msg.result_key } : {}),
        ...(msg.record_id !== undefined ? { record_id: msg.record_id } : {}),
      },
    }
  }

  function applyStatusSnapshot(snapshot: ExecutionStatusSnapshot) {
    state.value = snapshot.state
    lastResult.value = snapshot.last_result
    updateEnvironmentRecovery(snapshot.last_result)
    progress.value = snapshot.progress
    if (snapshot.node_statuses) {
      nodeStatuses.value = { ...snapshot.node_statuses }
    }
  }

  function applyExecutionComplete(payload: ExecutionResult) {
    state.value = 'idle'
    lastResult.value = payload
    updateEnvironmentRecovery(payload)
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
        logToLogger: !hasExistingFailureLog(nodeId, detail, fullDetail),
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
    environmentRecoveryAction,
    isEnvironmentRecoveryDialogVisible,
    isRunning,
    fetchStatus,
    run,
    stop,
    clear,
    dismissEnvironmentRecovery,
    applyProgress,
    applyNodeState,
    applyStatusSnapshot,
    applyExecutionComplete,
  }
})
