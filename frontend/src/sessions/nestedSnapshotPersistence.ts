import type { Ref } from 'vue'
import {
  deleteNestedWorkflowSnapshot,
  getNestedWorkflowSnapshot,
  putNestedWorkflowSnapshot,
  type NestedWorkflowSnapshotResponse,
} from '@/api/nestedWorkflowSnapshots'
import type { GraphState, ValidationResult } from '@/api/types'
import type { CanvasId, DisposableCanvasResource } from './canvasSessionRegistry'
import {
  createGraphSyncCoordinator,
  type GraphSyncCoordinator,
} from './graphSyncCoordinator'

export interface AcceptedNestedSnapshot {
  graph: GraphState
  validation: ValidationResult
  snapshotRevision: number
}

export interface NestedSnapshotPutRequest {
  sessionId: string
  expectedRevision: number
  graph: GraphState
  signal: AbortSignal
}

export interface NestedSnapshotDeleteRequest {
  sessionId: string
  expectedRevision: number
  signal: AbortSignal
}

export interface NestedSnapshotGetRequest {
  sessionId: string
  signal: AbortSignal
}

export interface NestedSnapshotPersistenceTransport {
  get(request: NestedSnapshotGetRequest): Promise<NestedWorkflowSnapshotResponse>
  put(request: NestedSnapshotPutRequest): Promise<NestedWorkflowSnapshotResponse>
  delete(request: NestedSnapshotDeleteRequest): Promise<void>
}

export interface NestedSnapshotPersistence extends DisposableCanvasResource {
  readonly coordinator: GraphSyncCoordinator
  readonly validationResult: Ref<ValidationResult | null>
  readonly currentGraph: Ref<GraphState>
  queue(graph: GraphState): number
  flushLatest(): Promise<AcceptedNestedSnapshot>
  resolveConflictKeepingLocal(): Promise<AcceptedNestedSnapshot>
  resolveConflictUsingRemote(): Promise<AcceptedNestedSnapshot>
  deleteLatest(): Promise<void>
}

export interface CreateNestedSnapshotPersistenceOptions {
  canvasId: CanvasId
  initialSnapshot: NestedWorkflowSnapshotResponse
  transport?: NestedSnapshotPersistenceTransport
  debounceMs?: number
  onAccepted?: (snapshot: NestedWorkflowSnapshotResponse) => void
}

const defaultTransport: NestedSnapshotPersistenceTransport = {
  get: ({ sessionId, signal }) => getNestedWorkflowSnapshot(sessionId, signal),
  put: ({ sessionId, expectedRevision, graph, signal }) => (
    putNestedWorkflowSnapshot(sessionId, {
      expected_revision: expectedRevision,
      graph,
    }, signal)
  ),
  delete: ({ sessionId, expectedRevision, signal }) => (
    deleteNestedWorkflowSnapshot(sessionId, expectedRevision, signal)
  ),
}

export class NestedSnapshotPersistenceConflictError extends Error {
  readonly expectedRevision: number
  readonly currentRevision: number | null
  readonly originalError: unknown

  constructor(options: {
    expectedRevision: number
    currentRevision: number | null
    detail: string
    originalError: unknown
  }) {
    super(options.detail)
    this.name = 'NestedSnapshotPersistenceConflictError'
    this.expectedRevision = options.expectedRevision
    this.currentRevision = options.currentRevision
    this.originalError = options.originalError
  }
}

export function isNestedSnapshotPersistenceConflict(
  error: unknown,
): error is NestedSnapshotPersistenceConflictError {
  return error instanceof NestedSnapshotPersistenceConflictError
}

function conflictResponse(error: unknown): {
  currentRevision: number | null
  detail: string
} | null {
  if (typeof error !== 'object' || error === null || !('response' in error)) {
    return null
  }
  const response = (error as {
    response?: {
      status?: unknown
      data?: { current_revision?: unknown; detail?: unknown }
    }
  }).response
  if (response?.status !== 409) return null
  return {
    currentRevision: typeof response.data?.current_revision === 'number'
      ? response.data.current_revision
      : null,
    detail: typeof response.data?.detail === 'string'
      && response.data.detail.trim().length > 0
      ? response.data.detail.trim()
      : 'The nested workflow snapshot changed elsewhere.',
  }
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function acceptedSnapshot(
  response: NestedWorkflowSnapshotResponse,
): AcceptedNestedSnapshot {
  return {
    graph: cloneJson(response.graph),
    validation: cloneJson(response.validation),
    snapshotRevision: response.snapshot_revision,
  }
}

export function createNestedSnapshotPersistence(
  options: CreateNestedSnapshotPersistenceOptions,
): NestedSnapshotPersistence {
  const transport = options.transport ?? defaultTransport
  let latestAccepted = cloneJson(options.initialSnapshot)
  let conflictResolution: {
    mode: 'keep-local' | 'use-remote'
    promise: Promise<AcceptedNestedSnapshot>
  } | null = null

  const coordinator = createGraphSyncCoordinator({
    canvasId: options.canvasId,
    workflowId: null,
    initialGraph: latestAccepted.graph,
    initialValidation: latestAccepted.validation,
    debounceMs: options.debounceMs,
    transport: async ({ graph, signal }) => {
      const expectedRevision = latestAccepted.snapshot_revision
      let response: NestedWorkflowSnapshotResponse
      try {
        response = await transport.put({
          sessionId: latestAccepted.session_id,
          expectedRevision,
          graph,
          signal,
        })
      } catch (error) {
        const conflict = conflictResponse(error)
        if (conflict === null) throw error
        throw new NestedSnapshotPersistenceConflictError({
          expectedRevision,
          currentRevision: conflict.currentRevision,
          detail: conflict.detail,
          originalError: error,
        })
      }
      if (response.session_id !== latestAccepted.session_id) {
        throw new Error('Nested snapshot response changed session identity')
      }
      if (response.snapshot_revision !== expectedRevision + 1) {
        throw new Error('Nested snapshot response returned an unexpected revision')
      }
      latestAccepted = cloneJson(response)
      options.onAccepted?.(cloneJson(response))
      return response.validation
    },
    isConflict: isNestedSnapshotPersistenceConflict,
  })

  async function flushLatest(): Promise<AcceptedNestedSnapshot> {
    await coordinator.flushLatest()
    return acceptedSnapshot(latestAccepted)
  }

  function startConflictResolution(
    mode: 'keep-local' | 'use-remote',
    resolve: (
      remote: NestedWorkflowSnapshotResponse,
    ) => Promise<AcceptedNestedSnapshot> | AcceptedNestedSnapshot,
  ): Promise<AcceptedNestedSnapshot> {
    if (conflictResolution !== null) {
      if (conflictResolution.mode === mode) return conflictResolution.promise
      return Promise.reject(new Error('Another nested snapshot resolution is in progress'))
    }
    const conflict = coordinator.lastError.value
    if (!isNestedSnapshotPersistenceConflict(conflict)) {
      return Promise.reject(new Error('Nested snapshot persistence has no conflict to resolve'))
    }
    const sessionId = latestAccepted.session_id
    const controller = new AbortController()
    const promise = (async () => {
      const remote = await transport.get({ sessionId, signal: controller.signal })
      if (remote.session_id !== sessionId) {
        throw new Error('Nested snapshot conflict resolution changed session identity')
      }
      if (
        conflict.currentRevision !== null
        && remote.snapshot_revision < conflict.currentRevision
      ) {
        throw new Error(
          `Nested snapshot conflict resolution returned stale revision ${remote.snapshot_revision}`,
        )
      }
      return resolve(remote)
    })().finally(() => {
      conflictResolution = null
    })
    conflictResolution = { mode, promise }
    return promise
  }

  function resolveConflictKeepingLocal(): Promise<AcceptedNestedSnapshot> {
    return startConflictResolution('keep-local', async (remote) => {
      latestAccepted = cloneJson(remote)
      options.onAccepted?.(cloneJson(remote))
      if (!coordinator.resumeAfterConflict()) {
        throw new Error('Nested snapshot conflict was resolved concurrently')
      }
      return flushLatest()
    })
  }

  function resolveConflictUsingRemote(): Promise<AcceptedNestedSnapshot> {
    return startConflictResolution('use-remote', (remote) => {
      latestAccepted = cloneJson(remote)
      options.onAccepted?.(cloneJson(remote))
      coordinator.acceptAuthoritativeSnapshot(remote.graph, remote.validation)
      return acceptedSnapshot(remote)
    })
  }

  async function deleteLatest(): Promise<void> {
    const accepted = await flushLatest()
    const controller = new AbortController()
    await transport.delete({
      sessionId: latestAccepted.session_id,
      expectedRevision: accepted.snapshotRevision,
      signal: controller.signal,
    })
  }

  return {
    coordinator,
    validationResult: coordinator.validationResult,
    currentGraph: coordinator.currentGraph,
    queue: graph => coordinator.queue(graph),
    flushLatest,
    resolveConflictKeepingLocal,
    resolveConflictUsingRemote,
    deleteLatest,
    dispose: coordinator.dispose,
  }
}
