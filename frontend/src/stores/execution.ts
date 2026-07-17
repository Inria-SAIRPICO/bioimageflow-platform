import { ref, computed, onScopeDispose } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import { useErrorReporting } from '@/composables/useErrorReporting'
import { useLoggerStore } from '@/stores/logger'
import { useUIStore } from '@/stores/ui'
import {
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'
import type {
  ExecutionResult,
  ExecutionStatus,
  GraphState,
  GraphValidationError,
  NodeStatus,
  ProgressInfo,
} from '@/api/types'

interface ExecutionContextFields {
  execution_id?: string | null
  workflow_id?: string | null
  draft_revision?: number | null
}

interface RequiredExecutionContextFields {
  execution_id: string
  workflow_id: string
  draft_revision: number | null
}

interface ExecutionWireContext {
  execution_id: string
  workflow_id: string
  draft_revision: number | null
}

interface NodeStateMessage extends RequiredExecutionContextFields {
  type?: 'node_state'
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
  execution_id?: string | null
  workflow_id?: string | null
  draft_revision?: number | null
}

interface ExecutionStatusSnapshot extends ExecutionStatus, ExecutionContextFields {
  type?: 'status_snapshot'
  node_statuses?: Record<string, NodeStatus>
}

interface ExecutionCompletePayload extends ExecutionResult, RequiredExecutionContextFields {
  type?: 'execution_complete'
}

interface ProgressPayload extends ProgressInfo, RequiredExecutionContextFields {
  type?: 'progress'
}

export interface RunExecutionOptions {
  canvasId: CanvasId | null
  draftRevision: number | null
}

interface PendingRun {
  requestId: number
  workflowId: string
  draftRevision: number | null | undefined
  canvasId: CanvasId | null
  graph: GraphState
  executionId: string | null
}

interface ClearResponse {
  node_statuses: Record<string, NodeStatus>
}

export type ExecutionPhase = 'idle' | 'starting' | 'running' | 'stopping'

const PROVISIONAL_STATUS_POLL_MS = 250

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
  context: RequiredExecutionContextFields,
): boolean {
  const logger = useLoggerStore()
  const errorText = detail.includes(': ') ? detail.split(': ').slice(1).join(': ') : detail
  const traceback = fullDetail?.split('\n').slice(1).join('\n') ?? ''
  return logger.entries.some((entry) => {
    if (entry.level !== 'ERROR') return false
    if ((nodeId ?? null) !== entry.nodeId) return false
    if (entry.executionId !== context.execution_id) return false
    if (entry.workflowId !== context.workflow_id) return false
    if (!entry.message.includes(errorText)) return false
    return !traceback || entry.message.includes(traceback)
  })
}

function executionContextFrom(
  value: ExecutionContextFields,
): ExecutionWireContext | null | undefined {
  const hasContextField = value.execution_id !== undefined
    || value.workflow_id !== undefined
    || value.draft_revision !== undefined
  if (!hasContextField) return undefined
  if (
    value.execution_id === null
    && value.workflow_id === null
    && value.draft_revision === null
  ) return undefined
  if (
    typeof value.execution_id !== 'string'
    || value.execution_id.length === 0
    || typeof value.workflow_id !== 'string'
    || value.workflow_id.length === 0
    || (
      value.draft_revision !== null
      && (
        typeof value.draft_revision !== 'number'
        || !Number.isInteger(value.draft_revision)
        || value.draft_revision < 0
      )
    )
  ) return null
  return {
    execution_id: value.execution_id,
    workflow_id: value.workflow_id,
    draft_revision: value.draft_revision,
  }
}

function sameExecutionContext(
  left: ExecutionWireContext,
  right: ExecutionWireContext,
): boolean {
  return left.execution_id === right.execution_id
    && left.workflow_id === right.workflow_id
    && left.draft_revision === right.draft_revision
}

function cloneGraph(graph: GraphState): GraphState {
  return JSON.parse(JSON.stringify(graph)) as GraphState
}

export const useExecutionStore = defineStore('execution', () => {
  const state = ref<ExecutionPhase>('idle')
  const lastResult = ref<ExecutionResult | null>(null)
  const progress = ref<ProgressInfo | null>(null)
  const nodeStatuses = ref<Record<string, NodeStatus>>({})
  const error = ref<string | null>(null)
  const isConflict = ref(false)
  const conflictCode = ref<string | null>(null)
  const validationErrors = ref<GraphValidationError[]>([])
  const environmentRecoveryAction = ref<EnvironmentRecoveryAction | null>(null)
  const dismissedEnvironmentRecoveryKey = ref<string | null>(null)
  const executionId = ref<string | null>(null)
  const executionWorkflowId = ref<string | null>(null)
  const executionDraftRevision = ref<number | null>(null)
  const originCanvasId = ref<CanvasId | null>(null)
  const originGraph = ref<GraphState | null>(null)

  let requestSequence = 0
  let activeStartRequest: number | null = null
  let activeStopRequest: number | null = null
  let terminalFence = false
  let pendingRun: PendingRun | null = null
  let provisionalContext: ExecutionWireContext | null = null
  let provisionalStatusPoll: ReturnType<typeof setTimeout> | null = null
  const terminalExecutionIds: string[] = []

  const isStarting = computed(() => state.value === 'starting')
  const isRunning = computed(() => state.value === 'running' || state.value === 'stopping')
  const isStopping = computed(() => state.value === 'stopping')
  const isMutationLocked = computed(() => state.value !== 'idle')
  const canStop = computed(() => state.value === 'running')
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

  function currentExecutionContext(): ExecutionWireContext | null {
    if (executionId.value === null || executionWorkflowId.value === null) return null
    return {
      execution_id: executionId.value,
      workflow_id: executionWorkflowId.value,
      draft_revision: executionDraftRevision.value,
    }
  }

  function matchesPendingRunContext(incoming: ExecutionWireContext): boolean {
    if (pendingRun === null) return false
    const revisionMatches = pendingRun.draftRevision === undefined
      || incoming.draft_revision === pendingRun.draftRevision
    return incoming.workflow_id === pendingRun.workflowId
      && revisionMatches
      && (
        pendingRun.executionId === null
        || incoming.execution_id === pendingRun.executionId
      )
  }

  function isTerminalExecution(executionId: string): boolean {
    return terminalExecutionIds.includes(executionId)
  }

  function rememberTerminalExecution(executionId: string): void {
    const existing = terminalExecutionIds.indexOf(executionId)
    if (existing >= 0) terminalExecutionIds.splice(existing, 1)
    terminalExecutionIds.push(executionId)
    if (terminalExecutionIds.length > 8) terminalExecutionIds.shift()
  }

  function clearRuntimeResult(): void {
    clearEnvironmentRecovery()
    lastResult.value = null
    progress.value = null
    nodeStatuses.value = {}
  }

  function clearProvisionalContext(): void {
    provisionalContext = null
    if (provisionalStatusPoll !== null) {
      clearTimeout(provisionalStatusPoll)
      provisionalStatusPoll = null
    }
  }

  function scheduleProvisionalStatusPoll(): void {
    if (
      provisionalContext === null
      || pendingRun !== null
      || provisionalStatusPoll !== null
    ) return
    provisionalStatusPoll = setTimeout(async () => {
      provisionalStatusPoll = null
      if (provisionalContext === null || pendingRun !== null) return
      await fetchStatus()
      scheduleProvisionalStatusPoll()
    }, PROVISIONAL_STATUS_POLL_MS)
  }

  onScopeDispose(clearProvisionalContext)

  function resolveOriginCanvas(workflowId: string): CanvasId | null {
    const ui = useUIStore()
    const activeCanvasId = canvasSessionRegistry.activeCanvasId.value
    if (
      activeCanvasId !== null
      && canvasSessionRegistry.get(activeCanvasId)?.descriptor.kind === 'root'
      && ui.canvasWorkflowId(activeCanvasId) === workflowId
    ) return activeCanvasId
    const matches = ui.canvasIdsForWorkflow(workflowId).filter(
      canvasId => canvasSessionRegistry.get(canvasId)?.descriptor.kind === 'root',
    )
    return matches.length === 1 ? matches[0]! : null
  }

  function resolveDeferredOriginCanvas(): CanvasId | null {
    if (originCanvasId.value !== null) return originCanvasId.value
    if (executionId.value === null || executionWorkflowId.value === null) return null
    const resolved = resolveOriginCanvas(executionWorkflowId.value)
    if (resolved !== null) originCanvasId.value = resolved
    return resolved
  }

  function adoptExecutionContext(
    context: ExecutionWireContext,
    canvasId: CanvasId | null,
    graph: GraphState | null,
  ): void {
    const previous = currentExecutionContext()
    const changed = previous === null || !sameExecutionContext(previous, context)
    if (
      changed
      && previous !== null
      && previous.execution_id !== context.execution_id
    ) {
      rememberTerminalExecution(previous.execution_id)
    }
    if (changed) clearRuntimeResult()
    if (changed) terminalFence = false
    executionId.value = context.execution_id
    executionWorkflowId.value = context.workflow_id
    executionDraftRevision.value = context.draft_revision
    originCanvasId.value = canvasId
    originGraph.value = graph === null ? null : cloneGraph(graph)
  }

  function acceptPayloadContext(
    payload: ExecutionContextFields,
    source: 'event' | 'response' | 'snapshot',
  ): boolean {
    const incoming = executionContextFrom(payload)
    if (incoming === undefined) {
      return source === 'snapshot'
        && executionId.value === null
        && pendingRun === null
        && state.value === 'idle'
    }
    if (incoming === null) return false

    if (
      source !== 'snapshot'
      && provisionalContext !== null
      && (
        pendingRun === null
        || sameExecutionContext(provisionalContext, incoming)
      )
    ) {
      clearProvisionalContext()
      if (pendingRun === null && state.value === 'starting') state.value = 'idle'
    }

    const current = currentExecutionContext()
    if (pendingRun !== null) {
      if (
        !matchesPendingRunContext(incoming)
        || (
          isTerminalExecution(incoming.execution_id)
          && !(
            source === 'response'
            && pendingRun.executionId === incoming.execution_id
          )
        )
      ) return false
      pendingRun.executionId = incoming.execution_id
      if (current === null || !sameExecutionContext(current, incoming)) {
        adoptExecutionContext(incoming, pendingRun.canvasId, pendingRun.graph)
      }
      return true
    }

    if (current !== null && sameExecutionContext(current, incoming)) {
      return source === 'snapshot'
        || !isTerminalExecution(incoming.execution_id)
    }
    if (isTerminalExecution(incoming.execution_id) || source === 'response') {
      return false
    }
    if (state.value !== 'idle') return false
    if (
      current !== null
      && current.workflow_id === incoming.workflow_id
      && current.draft_revision !== null
      && incoming.draft_revision !== null
      && incoming.draft_revision < current.draft_revision
    ) return false
    adoptExecutionContext(
      incoming,
      resolveOriginCanvas(incoming.workflow_id),
      null,
    )
    return true
  }

  function appliesToCanvas(canvasId: CanvasId): boolean {
    if (executionId.value === null) {
      return originCanvasId.value === canvasId
    }
    const session = canvasSessionRegistry.get(canvasId)
    if (
      session?.descriptor.kind !== 'root'
      || executionWorkflowId.value === null
      || useUIStore().canvasWorkflowId(canvasId) !== executionWorkflowId.value
    ) return false
    return resolveDeferredOriginCanvas() === canvasId
  }

  function applyBackendPhase(
    next: 'idle' | 'starting' | 'running',
    allowOwnedIdleWhileStarting = false,
  ): boolean {
    // An idle payload cannot describe the run whose start request still owns
    // this phase; reject its result, progress, and node statuses together.
    if (
      state.value === 'starting'
      && next === 'idle'
      && !allowOwnedIdleWhileStarting
    ) return false
    if (state.value === 'stopping' && next !== 'idle') return true
    if (state.value === 'idle' && terminalFence && next !== 'idle') return false
    const wasActive = state.value === 'running' || state.value === 'stopping'
    state.value = next
    if (next === 'idle' && wasActive) terminalFence = true
    return true
  }

  async function fetchStatus() {
    try {
      const { data } = await api.get<ExecutionStatusResponse>(
        '/api/v1/execution/status',
      )
      applyStatusSnapshot(data)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  async function run(
    graph: GraphState,
    nodes: string[] | undefined,
    workflowName: string,
    options?: RunExecutionOptions,
  ) {
    if (workflowName.trim().length === 0) {
      throw new Error('Workflow identity is required for execution')
    }
    if (state.value !== 'idle') {
      throw new Error('already running')
    }
    if (options?.canvasId !== null && options?.canvasId !== undefined) {
      if (
        typeof options.draftRevision !== 'number'
        || !Number.isInteger(options.draftRevision)
        || options.draftRevision < 0
      ) {
        throw new Error('An accepted draft revision is required for execution')
      }
    }
    const requestId = ++requestSequence
    const previousTerminalFence = terminalFence
    activeStartRequest = requestId
    terminalFence = false
    pendingRun = {
      requestId,
      workflowId: workflowName,
      draftRevision: options?.draftRevision,
      canvasId: options?.canvasId ?? null,
      graph: cloneGraph(graph),
      executionId: null,
    }
    state.value = 'starting'
    error.value = null
    isConflict.value = false
    conflictCode.value = null
    validationErrors.value = []
    try {
      const payload = {
        graph,
        nodes,
        workflow_name: workflowName,
        ...(options?.draftRevision !== undefined
          ? { draft_revision: options.draftRevision }
          : {}),
      }
      const { data } = await api.post<ExecutionContextFields & { status: string }>(
        '/api/v1/execution/run',
        payload,
      )
      if (activeStartRequest === requestId) {
        const responseContext = executionContextFrom(data)
        if (!acceptPayloadContext(data, 'response')) {
          throw new Error('Execution start returned a mismatched context')
        }
        if (responseContext === undefined) clearRuntimeResult()
        if (state.value === 'starting') state.value = 'running'
        pendingRun = null
      }
    } catch (e: unknown) {
      if (activeStartRequest === requestId) {
        const discoveredExecutionId = pendingRun?.requestId === requestId
          ? pendingRun.executionId
          : null
        if (state.value === 'starting') {
          state.value = 'idle'
          terminalFence = previousTerminalFence
          clearProvisionalContext()
        } else if (discoveredExecutionId === null) {
          terminalFence = previousTerminalFence
        } else if (isTerminalExecution(discoveredExecutionId)) {
          state.value = 'idle'
          terminalFence = true
        } else {
          terminalFence = false
        }
        if (pendingRun?.requestId === requestId) pendingRun = null
        const err = e as RunError
        const status = err.response?.status ?? err.status
        if (status === 409) {
          isConflict.value = true
          conflictCode.value = err.response?.data?.error ?? null
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
      }
      throw e
    } finally {
      if (activeStartRequest === requestId) activeStartRequest = null
    }
  }

  async function stop(): Promise<boolean> {
    if (state.value !== 'running') return false
    const requestId = ++requestSequence
    activeStopRequest = requestId
    state.value = 'stopping'
    try {
      await api.post('/api/v1/execution/stop')
      return true
    } catch (e: unknown) {
      if (activeStopRequest === requestId && state.value === 'stopping') {
        state.value = 'running'
      }
      throw e
    } finally {
      if (activeStopRequest === requestId) activeStopRequest = null
    }
  }

  async function clear(
    graph: GraphState,
    nodeIds: string[],
    workflowName: string,
  ) {
    if (workflowName.trim().length === 0) {
      throw new Error('Workflow identity is required for cache clearing')
    }
    const { data } = await api.post<ClearResponse>(
      '/api/v1/execution/clear',
      { graph, nodes: nodeIds, workflow_name: workflowName },
    )
    if (data?.node_statuses) {
      originCanvasId.value = resolveOriginCanvas(workflowName)
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

  function applyProgress(p: ProgressPayload) {
    if (!acceptPayloadContext(p, 'event')) return
    if (state.value === 'idle' && terminalFence) return
    if (state.value !== 'stopping') state.value = 'running'
    progress.value = p
  }

  function applyNodeState(msg: NodeStateMessage) {
    if (!acceptPayloadContext(msg, 'event')) return
    if (msg.status === 'running' && state.value === 'idle' && terminalFence) return
    if (msg.status === 'running' && state.value !== 'stopping') {
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
    const incoming = executionContextFrom(snapshot)
    if (snapshot.state === 'starting') {
      if (incoming === undefined || incoming === null) return
      if (pendingRun !== null) {
        if (!matchesPendingRunContext(incoming)) return
        pendingRun.executionId = incoming.execution_id
      } else {
        if (
          state.value !== 'idle'
          && provisionalContext === null
        ) return
        const current = currentExecutionContext()
        if (
          current !== null
          && current.workflow_id === incoming.workflow_id
          && current.draft_revision !== null
          && incoming.draft_revision !== null
          && incoming.draft_revision < current.draft_revision
        ) return
      }
      provisionalContext = incoming
      state.value = 'starting'
      scheduleProvisionalStatusPoll()
      return
    }

    if (provisionalContext !== null) {
      const matchesProvisional = incoming !== undefined
        && incoming !== null
        && sameExecutionContext(provisionalContext, incoming)
      if (
        snapshot.state === 'running'
        && !matchesProvisional
        && pendingRun !== null
      ) return
      clearProvisionalContext()
      if (pendingRun !== null && snapshot.state === 'idle' && !matchesProvisional) return
      if (pendingRun === null && state.value === 'starting') state.value = 'idle'
    }
    if (incoming === undefined && snapshot.state !== 'idle') return
    if (!acceptPayloadContext(snapshot, 'snapshot')) return
    const ownsPendingRun = incoming !== undefined
      && incoming !== null
      && pendingRun?.executionId === incoming.execution_id
    if (!applyBackendPhase(snapshot.state, ownsPendingRun)) return
    lastResult.value = snapshot.last_result
    updateEnvironmentRecovery(snapshot.last_result)
    progress.value = snapshot.progress
    if (snapshot.node_statuses) {
      nodeStatuses.value = { ...snapshot.node_statuses }
    }
    if (snapshot.state === 'idle' && executionId.value !== null) {
      terminalFence = true
      rememberTerminalExecution(executionId.value)
    }
  }

  function applyExecutionComplete(payload: ExecutionCompletePayload) {
    if (!acceptPayloadContext(payload, 'event')) return
    state.value = 'idle'
    terminalFence = true
    lastResult.value = payload
    updateEnvironmentRecovery(payload)
    progress.value = null
    if (payload.node_statuses) {
      nodeStatuses.value = { ...nodeStatuses.value, ...payload.node_statuses }
    }
    if (executionId.value !== null) rememberTerminalExecution(executionId.value)

    if (!payload.success) {
      _reportFailure(payload)
    }
  }

  function _reportFailure(payload: ExecutionCompletePayload): void {
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
      const alreadyLogged = hasExistingFailureLog(
        nodeId,
        detail,
        fullDetail,
        payload,
      )
      const { reportError } = useErrorReporting()
      reportError({
        kind: 'execution_failed',
        detail,
        ...(fullDetail ? { fullDetail } : {}),
        ...(nodeId ? { nodeId } : {}),
        logToLogger: false,
      })
      if (!alreadyLogged) {
        useLoggerStore().addEntry({
          level: 'ERROR',
          message: fullDetail ?? detail,
          nodeId: nodeId ?? null,
          timestamp: Date.now() / 1000,
          executionId: payload.execution_id,
          workflowId: payload.workflow_id,
          draftRevision: payload.draft_revision,
        })
      }
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
    conflictCode,
    validationErrors,
    environmentRecoveryAction,
    isEnvironmentRecoveryDialogVisible,
    isStarting,
    isRunning,
    isStopping,
    isMutationLocked,
    canStop,
    executionId,
    executionWorkflowId,
    executionDraftRevision,
    originCanvasId,
    originGraph,
    appliesToCanvas,
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
