import type {
  GraphState,
  PublishedInput,
  PublishedOutput,
  ValidationResult,
} from '@/api/types'
import type {
  NestedSnapshotOwner,
  NestedWorkflowSnapshotResponse,
} from '@/api/nestedWorkflowSnapshots'
import type {
  OpenDurableSubWorkflowSessionOptions,
  SubWorkflowSession,
  useSubWorkflowSessionsStore,
} from '@/stores/subWorkflowSessions'
import { makeGraph, makeValidationResult } from './graphFixtures'

interface ResolvedValueOnce<T> {
  mockResolvedValueOnce(value: T): unknown
}

type SubWorkflowSessionsStore = ReturnType<typeof useSubWorkflowSessionsStore>

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

function completeGraph(
  graph: GraphState,
  publishedInputs?: PublishedInput[],
  publishedOutputs?: PublishedOutput[],
): GraphState {
  return {
    ...clone(graph),
    published_inputs: clone(publishedInputs ?? graph.published_inputs ?? []),
    published_outputs: clone(publishedOutputs ?? graph.published_outputs ?? []),
  }
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
    OpenDurableSubWorkflowSessionOptions,
    'owner' | 'parentCanvasId' | 'parentWorkflowName' | 'parentNodeId'
    | 'parentNodeName' | 'graph' | 'published_inputs' | 'published_outputs'
  > {
  owner?: NestedSnapshotOwner
  parentCanvasId?: string
  parentWorkflowName?: string | null
  parentNodeId?: string
  parentNodeName?: string
  graph?: GraphState
  published_inputs?: PublishedInput[]
  published_outputs?: PublishedOutput[]
  acceptedGraph?: GraphState
  sessionId?: string
  snapshotRevision?: number
  updatedAt?: string
  validation?: ValidationResult
}

/** Opens a real durable store session from one mocked, server-accepted snapshot. */
export async function openAcceptedNestedSession(
  store: SubWorkflowSessionsStore,
  openSnapshot: ResolvedValueOnce<NestedWorkflowSnapshotResponse>,
  options: AcceptedNestedSessionOptions = {},
): Promise<SubWorkflowSession> {
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
  const parentGraph = completeGraph(
    options.graph ?? makeGraph(),
    options.published_inputs,
    options.published_outputs,
  )
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
    readonlyReason: options.readonlyReason,
  })
}
