import type {
  GraphState,
  ValidationResult,
} from '@/api/types'
import type {
  NestedSnapshotOwner,
  NestedWorkflowSnapshotResponse,
} from '@/api/nestedWorkflowSnapshots'
import type {
  OpenDurableNestedWorkflowSessionOptions,
  NestedWorkflowSession,
  useNestedWorkflowSessionsStore,
} from '@/stores/nestedWorkflowSessions'
import { makeGraph, makeValidationResult } from './graphFixtures'

interface ResolvedValueOnce<T> {
  mockResolvedValueOnce(value: T): unknown
}

type NestedWorkflowSessionsStore = ReturnType<typeof useNestedWorkflowSessionsStore>

export interface AcceptedNestedSnapshotOptions {
  sessionId?: string
  owner?: NestedSnapshotOwner
  parentNodeId?: string
  graph?: GraphState
  snapshotRevision?: number
  updatedAt?: string
  validation?: ValidationResult
}

let fixtureSequence = 0

function nextSessionId(): string {
  fixtureSequence += 1
  return `00000000-0000-4000-8000-${fixtureSequence.toString().padStart(12, '0')}`
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function completeGraph(graph: GraphState): GraphState {
  return clone(graph)
}

export function makeAcceptedNestedSnapshot(
  options: AcceptedNestedSnapshotOptions = {},
): NestedWorkflowSnapshotResponse {
  const parentCanvasId = 'workflow:parent'
  return {
    snapshot_version: 1,
    session_id: options.sessionId ?? nextSessionId(),
    owner: clone(options.owner ?? {
      kind: 'root',
      canvas_id: parentCanvasId,
      workflow_id: 'parent',
    }),
    parent_node_id: options.parentNodeId ?? 'sub_1',
    snapshot_revision: options.snapshotRevision ?? 1,
    updated_at: options.updatedAt ?? '2026-07-16T00:00:00Z',
    graph: completeGraph(options.graph ?? makeGraph()),
    validation: clone(options.validation ?? makeValidationResult()),
  }
}

export interface AcceptedNestedSessionOptions
  extends Omit<
    OpenDurableNestedWorkflowSessionOptions,
    'owner' | 'parentCanvasId' | 'parentWorkflowName' | 'parentNodeId'
    | 'parentNodeName' | 'graph'
  > {
  owner?: NestedSnapshotOwner
  parentCanvasId?: string
  parentWorkflowName?: string | null
  parentNodeId?: string
  parentNodeName?: string
  graph?: GraphState
  acceptedGraph?: GraphState
  sessionId?: string
  snapshotRevision?: number
  updatedAt?: string
  validation?: ValidationResult
}

/** Opens a real durable store session from one mocked, server-accepted snapshot. */
export async function openAcceptedNestedSession(
  store: NestedWorkflowSessionsStore,
  openSnapshot: ResolvedValueOnce<NestedWorkflowSnapshotResponse>,
  options: AcceptedNestedSessionOptions = {},
): Promise<NestedWorkflowSession> {
  const parentCanvasId = options.parentCanvasId ?? 'workflow:parent'
  const parentWorkflowName = options.parentWorkflowName === undefined
    ? 'parent'
    : options.parentWorkflowName
  const parentNodeId = options.parentNodeId ?? 'sub_1'
  const owner = options.owner ?? {
    kind: 'root' as const,
    canvas_id: parentCanvasId,
    workflow_id: parentWorkflowName,
  }
  const parentGraph = completeGraph(options.graph ?? makeGraph())
  const acceptedGraph = completeGraph(
    options.acceptedGraph ?? parentGraph,
  )
  const snapshot = makeAcceptedNestedSnapshot({
    sessionId: options.sessionId,
    owner,
    parentNodeId,
    graph: acceptedGraph,
    snapshotRevision: options.snapshotRevision,
    updatedAt: options.updatedAt,
    validation: options.validation,
  })
  openSnapshot.mockResolvedValueOnce(snapshot)

  return store.openDurableSession({
    owner,
    parentCanvasId,
    parentWorkflowName,
    parentSourceWorkflowName: options.parentSourceWorkflowName,
    parentNodeId,
    parentNodeName: options.parentNodeName ?? 'Sub 1',
    graph: parentGraph,
  })
}
