import type { Ref } from 'vue'
import {
  deleteNestedWorkflowSnapshot,
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

export interface NestedSnapshotPersistenceTransport {
  put(request: NestedSnapshotPutRequest): Promise<NestedWorkflowSnapshotResponse>
  delete(request: NestedSnapshotDeleteRequest): Promise<void>
}

export interface NestedSnapshotPersistence extends DisposableCanvasResource {
  readonly coordinator: GraphSyncCoordinator
  readonly validationResult: Ref<ValidationResult | null>
  readonly currentGraph: Ref<GraphState>
  queue(graph: GraphState): number
  flushLatest(): Promise<AcceptedNestedSnapshot>
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

  const coordinator = createGraphSyncCoordinator({
    canvasId: options.canvasId,
    workflowId: null,
    initialGraph: latestAccepted.graph,
    initialValidation: latestAccepted.validation,
    debounceMs: options.debounceMs,
    transport: async ({ graph, signal }) => {
      const expectedRevision = latestAccepted.snapshot_revision
      const response = await transport.put({
        sessionId: latestAccepted.session_id,
        expectedRevision,
        graph,
        signal,
      })
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
  })

  async function flushLatest(): Promise<AcceptedNestedSnapshot> {
    await coordinator.flushLatest()
    return acceptedSnapshot(latestAccepted)
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
    deleteLatest,
    dispose: coordinator.dispose,
  }
}
