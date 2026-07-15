import { ref, type Ref } from 'vue'
import type { GraphState, ValidationResult } from '@/api/types'
import type { CanvasId, DisposableCanvasResource } from './canvasSessionRegistry'

export type SyncState = 'idle' | 'pending' | 'error'

export interface GraphSyncRequest {
  canvasId: CanvasId
  workflowId: string | null
  semanticRevision: number
  graph: GraphState
  signal: AbortSignal
}

export type GraphSyncTransport = (
  request: GraphSyncRequest,
) => Promise<ValidationResult>

export interface GraphSyncAcceptance {
  canvasId: CanvasId
  workflowId: string | null
  semanticRevision: number
  graph: GraphState
  validation: ValidationResult
}

export interface QueueGraphOptions {
  semanticRevision?: number
  /** Compatibility escape hatch; canvas sessions leave this unset. */
  workflowId?: string | null
}

export interface GraphSyncCoordinator extends DisposableCanvasResource {
  readonly canvasId: CanvasId
  readonly workflowId: string | null
  readonly validationResult: Ref<ValidationResult | null>
  readonly currentGraph: Ref<GraphState>
  readonly semanticRevision: Ref<number>
  readonly acceptedRevision: Ref<number | null>
  readonly isPending: Ref<boolean>
  readonly syncState: Ref<SyncState>
  readonly isDisposed: Ref<boolean>
  queue(graph: GraphState, options?: QueueGraphOptions): number
  flushLatest(): Promise<GraphSyncAcceptance | null>
}

export interface CreateGraphSyncCoordinatorOptions {
  canvasId: CanvasId
  workflowId: string | null
  transport: GraphSyncTransport
  debounceMs?: number
  initialGraph?: GraphState
  initialSemanticRevision?: number
  onOperationalError?: (
    error: unknown,
    request: Omit<GraphSyncRequest, 'signal'>,
  ) => void
}

interface QueuedGraph {
  canvasId: CanvasId
  workflowId: string | null
  semanticRevision: number
  graph: GraphState
}

interface InflightGraph {
  snapshot: QueuedGraph
  controller: AbortController
  promise: Promise<GraphSyncAcceptance>
}

export class CanvasSessionDisposedError extends Error {
  constructor(canvasId: CanvasId) {
    super(`Canvas session '${canvasId}' has been disposed`)
    this.name = 'CanvasSessionDisposedError'
  }
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export function createGraphSyncCoordinator(
  options: CreateGraphSyncCoordinatorOptions,
): GraphSyncCoordinator {
  const debounceMs = options.debounceMs ?? 300
  const validationResult = ref<ValidationResult | null>(null)
  const currentGraph = ref<GraphState>(cloneJson(
    options.initialGraph ?? { nodes: [], edges: [] },
  )) as Ref<GraphState>
  const semanticRevision = ref(options.initialSemanticRevision ?? 0)
  const acceptedRevision = ref<number | null>(null)
  const isPending = ref(false)
  const syncState = ref<SyncState>('idle')
  const isDisposed = ref(false)

  let latest: QueuedGraph | null = null
  let lastAcceptance: GraphSyncAcceptance | null = null
  let timer: ReturnType<typeof setTimeout> | null = null
  let inflight: InflightGraph | null = null
  let rejectDisposed!: (reason: CanvasSessionDisposedError) => void
  const disposedPromise = new Promise<never>((_resolve, reject) => {
    rejectDisposed = reject
  })
  // A coordinator may be disposed while idle, when nobody is awaiting this.
  void disposedPromise.catch(() => {})

  function assertUsable(): void {
    if (isDisposed.value) {
      throw new CanvasSessionDisposedError(options.canvasId)
    }
  }

  function clearTimer(): void {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  function queue(graph: GraphState, queueOptions: QueueGraphOptions = {}): number {
    assertUsable()
    const nextRevision = queueOptions.semanticRevision
      ?? semanticRevision.value + 1
    if (nextRevision <= semanticRevision.value) {
      throw new Error(
        `Semantic revision ${nextRevision} must be newer than ${semanticRevision.value}`,
      )
    }

    const graphSnapshot = cloneJson(graph)
    latest = {
      canvasId: options.canvasId,
      workflowId: queueOptions.workflowId === undefined
        ? options.workflowId
        : queueOptions.workflowId,
      semanticRevision: nextRevision,
      graph: graphSnapshot,
    }
    currentGraph.value = cloneJson(graphSnapshot)
    semanticRevision.value = nextRevision
    isPending.value = true
    syncState.value = 'pending'

    clearTimer()
    timer = setTimeout(() => {
      timer = null
      void flushLatest().catch(() => {
        // State and reporting are handled by send(); explicit flush callers reject.
      })
    }, debounceMs)
    return nextRevision
  }

  function startSend(snapshot: QueuedGraph): InflightGraph {
    isPending.value = true
    syncState.value = 'pending'
    const controller = new AbortController()
    const request = {
      canvasId: snapshot.canvasId,
      workflowId: snapshot.workflowId,
      semanticRevision: snapshot.semanticRevision,
      graph: cloneJson(snapshot.graph),
      signal: controller.signal,
    }
    const transportPromise = Promise.resolve().then(() => options.transport(request))
    const promise = Promise.race([transportPromise, disposedPromise])
      .then((validation): GraphSyncAcceptance => {
        const acceptance: GraphSyncAcceptance = {
          canvasId: snapshot.canvasId,
          workflowId: snapshot.workflowId,
          semanticRevision: snapshot.semanticRevision,
          graph: cloneJson(snapshot.graph),
          validation: cloneJson(validation),
        }
        if (
          acceptedRevision.value === null
          || snapshot.semanticRevision > acceptedRevision.value
        ) {
          acceptedRevision.value = snapshot.semanticRevision
          lastAcceptance = acceptance
        }
        if (latest?.semanticRevision === snapshot.semanticRevision) {
          validationResult.value = cloneJson(validation)
          isPending.value = false
          syncState.value = 'idle'
        } else {
          isPending.value = true
          syncState.value = 'pending'
        }
        return acceptance
      })
      .catch((error: unknown) => {
        if (isDisposed.value) {
          throw new CanvasSessionDisposedError(options.canvasId)
        }
        const isCurrentRevision = latest?.semanticRevision === snapshot.semanticRevision
        if (isCurrentRevision) {
          isPending.value = false
          syncState.value = 'error'
        } else {
          isPending.value = true
          syncState.value = 'pending'
        }
        if (isCurrentRevision) {
          options.onOperationalError?.(error, {
            canvasId: request.canvasId,
            workflowId: request.workflowId,
            semanticRevision: request.semanticRevision,
            graph: request.graph,
          })
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

  async function flushLatest(): Promise<GraphSyncAcceptance | null> {
    assertUsable()
    clearTimer()

    while (true) {
      assertUsable()
      const target = latest
      if (target === null) return lastAcceptance
      if (
        acceptedRevision.value !== null
        && acceptedRevision.value >= target.semanticRevision
      ) {
        return lastAcceptance
      }

      const activeRequest = inflight ?? startSend(target)
      try {
        await activeRequest.promise
      } catch (error) {
        const newer = latest
        if (
          !isDisposed.value
          && newer !== null
          && newer.semanticRevision > activeRequest.snapshot.semanticRevision
        ) {
          continue
        }
        throw error
      }
      // The loop re-reads latest after joining, so edits made during the
      // request are sent before the flush resolves.
    }
  }

  function dispose(): void {
    if (isDisposed.value) return
    isDisposed.value = true
    clearTimer()
    const error = new CanvasSessionDisposedError(options.canvasId)
    rejectDisposed(error)
    inflight?.controller.abort()
    isPending.value = false
    syncState.value = 'idle'
  }

  return {
    canvasId: options.canvasId,
    workflowId: options.workflowId,
    validationResult,
    currentGraph,
    semanticRevision,
    acceptedRevision,
    isPending,
    syncState,
    isDisposed,
    queue,
    flushLatest,
    dispose,
  }
}
