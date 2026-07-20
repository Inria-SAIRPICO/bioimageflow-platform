import { ref, shallowRef, type Ref, type ShallowRef } from 'vue'
import type { GraphState } from '@/api/types'
import { emptyGraph } from '@/sessions/graphDocument'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import type { CanvasId, DisposableCanvasResource } from './canvasSessionRegistry'

export type WorkflowDraftSyncState = 'idle' | 'pending' | 'error' | 'conflict'

export interface WorkflowDraftWriteRequest {
  canvasId: CanvasId
  workflowId: string
  queueRevision: number
  expectedDraftRevision: number
  graph: GraphState
  signal: AbortSignal
}

export type WorkflowDraftTransport = (
  request: WorkflowDraftWriteRequest,
) => Promise<WorkflowDraftResponse>

export interface WorkflowDraftAcceptance {
  canvasId: CanvasId
  workflowId: string
  queueRevision: number
  graph: GraphState
  expectedDraftRevision: number
  draftRevision: number
  response: WorkflowDraftResponse
}

export interface WorkflowDraftCoordinator extends DisposableCanvasResource {
  readonly canvasId: CanvasId
  readonly workflowId: string
  readonly currentGraph: Ref<GraphState>
  readonly queueRevision: Ref<number>
  readonly acceptedQueueRevision: Ref<number | null>
  readonly currentDraftRevision: Ref<number>
  readonly conflictDraftRevision: Ref<number | null>
  readonly lastError: ShallowRef<unknown | null>
  readonly isPending: Ref<boolean>
  readonly syncState: Ref<WorkflowDraftSyncState>
  readonly isDisposed: Ref<boolean>
  queue(graph: GraphState): number
  flushLatest(): Promise<WorkflowDraftAcceptance | null>
}

export interface CreateWorkflowDraftCoordinatorOptions {
  canvasId: CanvasId
  workflowId: string
  initialDraftRevision: number
  transport: WorkflowDraftTransport
  debounceMs?: number
  onOperationalError?: (
    error: unknown,
    request: Omit<WorkflowDraftWriteRequest, 'signal'>,
  ) => void
  onAccepted?: (acceptance: WorkflowDraftAcceptance) => void
}

interface QueuedDraft {
  canvasId: CanvasId
  workflowId: string
  queueRevision: number
  graph: GraphState
}

interface InflightDraft {
  snapshot: QueuedDraft
  controller: AbortController
  promise: Promise<WorkflowDraftAcceptance>
}

export class WorkflowDraftCoordinatorDisposedError extends Error {
  constructor(canvasId: CanvasId) {
    super(`Workflow draft coordinator for canvas '${canvasId}' has been disposed`)
    this.name = 'WorkflowDraftCoordinatorDisposedError'
  }
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function conflictRevision(error: unknown): number | null {
  if (typeof error !== 'object' || error === null || !('response' in error)) {
    return null
  }
  const response = (error as {
    response?: { status?: unknown; data?: { current_revision?: unknown } }
  }).response
  if (response?.status !== 409) return null
  const revision = response.data?.current_revision
  return typeof revision === 'number' ? revision : null
}

export function createWorkflowDraftCoordinator(
  options: CreateWorkflowDraftCoordinatorOptions,
): WorkflowDraftCoordinator {
  const debounceMs = options.debounceMs ?? 500
  const currentGraph = ref<GraphState>(emptyGraph()) as Ref<GraphState>
  const queueRevision = ref(0)
  const acceptedQueueRevision = ref<number | null>(null)
  const currentDraftRevision = ref(options.initialDraftRevision)
  const conflictDraftRevision = ref<number | null>(null)
  const lastError = shallowRef<unknown | null>(null)
  const isPending = ref(false)
  const syncState = ref<WorkflowDraftSyncState>('idle')
  const isDisposed = ref(false)

  let latest: QueuedDraft | null = null
  let lastAcceptance: WorkflowDraftAcceptance | null = null
  let timer: ReturnType<typeof setTimeout> | null = null
  let inflight: InflightDraft | null = null
  let rejectDisposed!: (reason: WorkflowDraftCoordinatorDisposedError) => void
  const disposedPromise = new Promise<never>((_resolve, reject) => {
    rejectDisposed = reject
  })
  void disposedPromise.catch(() => {})

  function assertUsable(): void {
    if (isDisposed.value) {
      throw new WorkflowDraftCoordinatorDisposedError(options.canvasId)
    }
  }

  function clearTimer(): void {
    if (timer === null) return
    clearTimeout(timer)
    timer = null
  }

  function queue(graph: GraphState): number {
    assertUsable()
    const hasConflict = conflictDraftRevision.value !== null
    const nextRevision = queueRevision.value + 1
    const graphSnapshot = cloneJson(graph)
    latest = {
      canvasId: options.canvasId,
      workflowId: options.workflowId,
      queueRevision: nextRevision,
      graph: graphSnapshot,
    }
    queueRevision.value = nextRevision
    currentGraph.value = cloneJson(graphSnapshot)
    isPending.value = true
    clearTimer()
    if (hasConflict) {
      syncState.value = 'conflict'
      return nextRevision
    }

    syncState.value = 'pending'
    lastError.value = null
    timer = setTimeout(() => {
      timer = null
      void flushLatest().catch(() => {
        // State and reporting are handled by the active write.
      })
    }, debounceMs)
    return nextRevision
  }

  function startWrite(snapshot: QueuedDraft): InflightDraft {
    isPending.value = true
    syncState.value = 'pending'
    const expectedDraftRevision = currentDraftRevision.value
    const controller = new AbortController()
    const request: WorkflowDraftWriteRequest = {
      canvasId: snapshot.canvasId,
      workflowId: snapshot.workflowId,
      queueRevision: snapshot.queueRevision,
      expectedDraftRevision,
      graph: cloneJson(snapshot.graph),
      signal: controller.signal,
    }
    const transportPromise = Promise.resolve().then(() => options.transport(request))
    const promise = Promise.race([transportPromise, disposedPromise])
      .then((response): WorkflowDraftAcceptance => {
        const acceptance: WorkflowDraftAcceptance = {
          canvasId: snapshot.canvasId,
          workflowId: snapshot.workflowId,
          queueRevision: snapshot.queueRevision,
          graph: cloneJson(snapshot.graph),
          expectedDraftRevision,
          draftRevision: response.draft_revision,
          response: cloneJson(response),
        }
        currentDraftRevision.value = response.draft_revision
        acceptedQueueRevision.value = snapshot.queueRevision
        lastAcceptance = acceptance
        lastError.value = null
        conflictDraftRevision.value = null

        if (latest?.queueRevision === snapshot.queueRevision) {
          isPending.value = false
          syncState.value = 'idle'
          options.onAccepted?.(cloneJson(acceptance))
        } else {
          isPending.value = true
          syncState.value = 'pending'
        }
        return acceptance
      })
      .catch((error: unknown) => {
        if (isDisposed.value) {
          throw new WorkflowDraftCoordinatorDisposedError(options.canvasId)
        }
        const conflict = conflictRevision(error)
        const isCurrent = latest?.queueRevision === snapshot.queueRevision
        isPending.value = true
        if (conflict !== null) {
          clearTimer()
          lastError.value = error
          conflictDraftRevision.value = conflict
          syncState.value = 'conflict'
        } else if (isCurrent) {
          lastError.value = error
          syncState.value = 'error'
          options.onOperationalError?.(error, {
            canvasId: request.canvasId,
            workflowId: request.workflowId,
            queueRevision: request.queueRevision,
            expectedDraftRevision: request.expectedDraftRevision,
            graph: request.graph,
          })
        } else {
          syncState.value = 'pending'
        }
        throw error
      })
      .finally(() => {
        if (inflight?.promise === promise) {
          inflight = null
        }
      })

    const started = { snapshot, controller, promise }
    inflight = started
    return started
  }

  async function flushLatest(): Promise<WorkflowDraftAcceptance | null> {
    assertUsable()
    clearTimer()
    if (conflictDraftRevision.value !== null && lastError.value !== null) {
      throw lastError.value
    }

    while (true) {
      assertUsable()
      const target = latest
      if (target === null) return lastAcceptance
      if (
        acceptedQueueRevision.value !== null
        && acceptedQueueRevision.value >= target.queueRevision
      ) {
        return lastAcceptance
      }

      const activeWrite = inflight ?? startWrite(target)
      try {
        await activeWrite.promise
      } catch (error) {
        const newer = latest
        if (
          conflictRevision(error) === null
          && !isDisposed.value
          && newer !== null
          && newer.queueRevision > activeWrite.snapshot.queueRevision
        ) {
          continue
        }
        throw error
      }
    }
  }

  function dispose(): void {
    if (isDisposed.value) return
    isDisposed.value = true
    clearTimer()
    rejectDisposed(new WorkflowDraftCoordinatorDisposedError(options.canvasId))
    inflight?.controller.abort()
    isPending.value = false
    syncState.value = 'idle'
  }

  return {
    canvasId: options.canvasId,
    workflowId: options.workflowId,
    currentGraph,
    queueRevision,
    acceptedQueueRevision,
    currentDraftRevision,
    conflictDraftRevision,
    lastError,
    isPending,
    syncState,
    isDisposed,
    queue,
    flushLatest,
    dispose,
  }
}
