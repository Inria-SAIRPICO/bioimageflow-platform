import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  deleteNestedWorkflowSnapshot,
  openNestedWorkflowSnapshot,
  type NestedSnapshotOwner,
  type NestedWorkflowSnapshotResponse,
} from '@/api/nestedWorkflowSnapshots'
import type {
  GraphState,
  PublishedInput,
  PublishedOutput,
  ValidationResult,
} from '@/api/types'
import { graphDocumentsEqual } from '@/sessions/graphDocument'

export interface SubWorkflowSession {
  id: string
  owner: NestedSnapshotOwner
  parentCanvasId: string
  parentWorkflowName: string | null
  parentSourceWorkflowName: string | null
  parentNodeId: string
  parentNodeName: string
  draft: GraphState
  savedSnapshot: GraphState
  acceptedSnapshot: GraphState
  snapshotRevision: number
  updatedAt: string
  validation: ValidationResult
  durable: boolean
  /** Compatibility views backed directly by draft, not separate state. */
  published_inputs: PublishedInput[]
  published_outputs: PublishedOutput[]
}

export interface OpenSubWorkflowSessionOptions {
  id?: string
  owner?: NestedSnapshotOwner
  parentCanvasId?: string
  parentWorkflowName: string | null
  parentSourceWorkflowName?: string | null
  parentNodeId: string
  parentNodeName: string
  graph: GraphState
  published_inputs?: PublishedInput[]
  published_outputs?: PublishedOutput[]
  snapshotRevision?: number
  validation?: ValidationResult
  durable?: boolean
  readonlyReason?: string | null
}

export interface OpenDurableSubWorkflowSessionOptions
  extends Omit<OpenSubWorkflowSessionOptions, 'id' | 'durable' | 'owner'> {
  owner: NestedSnapshotOwner
  parentCanvasId: string
}

export interface SavedSubWorkflowSession {
  graph: GraphState
  published_inputs: PublishedInput[]
  published_outputs: PublishedOutput[]
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function completeGraph(
  graph: GraphState,
  publishedInputs?: PublishedInput[],
  publishedOutputs?: PublishedOutput[],
): GraphState {
  return {
    ...deepClone(graph),
    published_inputs: deepClone(publishedInputs ?? graph.published_inputs ?? []),
    published_outputs: deepClone(publishedOutputs ?? graph.published_outputs ?? []),
  }
}

function defaultValidation(): ValidationResult {
  return { valid: true, node_statuses: {}, errors: [] }
}

let fallbackSessionSequence = 0

function newSessionId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  fallbackSessionSequence += 1
  return `local-nested-session-${fallbackSessionSequence}`
}

function sameOwner(left: NestedSnapshotOwner, right: NestedSnapshotOwner): boolean {
  if (left.kind !== right.kind) return false
  if (left.kind === 'root' && right.kind === 'root') {
    return left.canvas_id === right.canvas_id
      && (left.workflow_id ?? null) === (right.workflow_id ?? null)
  }
  return left.kind === 'nested'
    && right.kind === 'nested'
    && left.session_id === right.session_id
}

function createSession(
  options: OpenSubWorkflowSessionOptions,
  draft: GraphState,
  savedSnapshot: GraphState,
): SubWorkflowSession {
  const parentCanvasId = options.parentCanvasId
    ?? (options.parentWorkflowName ? `workflow:${options.parentWorkflowName}` : 'canvas')
  const session = {
    id: options.id ?? newSessionId(),
    owner: options.owner ?? {
      kind: 'root',
      canvas_id: parentCanvasId,
      workflow_id: options.parentWorkflowName,
    },
    parentCanvasId,
    parentWorkflowName: options.parentWorkflowName,
    parentSourceWorkflowName: options.parentSourceWorkflowName ?? null,
    parentNodeId: options.parentNodeId,
    parentNodeName: options.parentNodeName,
    draft,
    savedSnapshot,
    acceptedSnapshot: deepClone(draft),
    snapshotRevision: options.snapshotRevision ?? 0,
    updatedAt: new Date().toISOString(),
    validation: deepClone(options.validation ?? defaultValidation()),
    durable: options.durable ?? false,
  } as SubWorkflowSession

  Object.defineProperties(session, {
    published_inputs: {
      enumerable: true,
      get: () => session.draft.published_inputs ?? [],
      set: (value: PublishedInput[]) => {
        session.draft.published_inputs = deepClone(value)
      },
    },
    published_outputs: {
      enumerable: true,
      get: () => session.draft.published_outputs ?? [],
      set: (value: PublishedOutput[]) => {
        session.draft.published_outputs = deepClone(value)
      },
    },
  })
  return session
}

export const useSubWorkflowSessionsStore = defineStore('subWorkflowSessions', () => {
  const sessions = ref<SubWorkflowSession[]>([])

  const dirtySessionIds = computed(() => sessions.value
    .filter((session) => isSessionDirty(session))
    .map((session) => session.id))

  function isSessionDirty(session: SubWorkflowSession): boolean {
    return !graphDocumentsEqual(session.draft, session.savedSnapshot)
  }

  function sessionById(id: string): SubWorkflowSession | undefined {
    return sessions.value.find((session) => session.id === id)
  }

  function openSession(options: OpenSubWorkflowSessionOptions): SubWorkflowSession {
    if (options.readonlyReason) {
      throw new Error(options.readonlyReason)
    }
    if (options.id) {
      const existing = sessionById(options.id)
      if (existing) return existing
    }

    const graph = completeGraph(
      options.graph,
      options.published_inputs,
      options.published_outputs,
    )
    const session = createSession(options, graph, deepClone(graph))
    sessions.value = [...sessions.value, session]
    return sessionById(session.id)!
  }

  async function openDurableSession(
    options: OpenDurableSubWorkflowSessionOptions,
  ): Promise<SubWorkflowSession> {
    if (options.readonlyReason) {
      throw new Error(options.readonlyReason)
    }
    const existing = sessions.value.find(session => (
      session.durable
      && session.parentNodeId === options.parentNodeId
      && sameOwner(session.owner, options.owner)
    ))
    if (existing) return existing

    const parentBaseline = completeGraph(
      options.graph,
      options.published_inputs,
      options.published_outputs,
    )
    const snapshot = await openNestedWorkflowSnapshot({
      owner: options.owner,
      parent_node_id: options.parentNodeId,
      graph: parentBaseline,
    })
    const concurrentlyOpened = sessionById(snapshot.session_id)
    if (concurrentlyOpened) return concurrentlyOpened
    const session = createSession({
      ...options,
      id: snapshot.session_id,
      owner: snapshot.owner,
      graph: snapshot.graph,
      snapshotRevision: snapshot.snapshot_revision,
      validation: snapshot.validation,
      durable: true,
    }, completeGraph(snapshot.graph), parentBaseline)
    session.updatedAt = snapshot.updated_at
    sessions.value = [...sessions.value, session]
    return sessionById(session.id)!
  }

  function isDirty(id: string): boolean {
    const session = sessionById(id)
    return session ? isSessionDirty(session) : false
  }

  function markSaved(
    id: string,
    graph: GraphState,
    snapshotRevision?: number | null,
    validation?: ValidationResult,
  ): void {
    const session = sessionById(id)
    if (!session) throw new Error(`Sub-workflow session not found: ${id}`)
    const accepted = completeGraph(graph)
    session.draft = deepClone(accepted)
    session.savedSnapshot = deepClone(accepted)
    if (snapshotRevision !== null && snapshotRevision !== undefined) {
      session.snapshotRevision = snapshotRevision
    }
    if (validation) session.validation = deepClone(validation)
    session.acceptedSnapshot = deepClone(accepted)
  }

  function saveSession(id: string): SavedSubWorkflowSession {
    const session = sessionById(id)
    if (!session) throw new Error(`Sub-workflow session not found: ${id}`)
    markSaved(id, session.draft)
    return {
      graph: deepClone(session.draft),
      published_inputs: deepClone(session.draft.published_inputs ?? []),
      published_outputs: deepClone(session.draft.published_outputs ?? []),
    }
  }

  function updateDraft(id: string, graph: GraphState): void {
    const session = sessionById(id)
    if (!session) throw new Error(`Sub-workflow session not found: ${id}`)
    session.draft = completeGraph(graph)
  }

  function acceptSnapshot(
    id: string,
    snapshot: NestedWorkflowSnapshotResponse,
  ): void {
    const session = sessionById(id)
    if (!session || snapshot.snapshot_revision < session.snapshotRevision) return
    session.snapshotRevision = snapshot.snapshot_revision
    session.updatedAt = snapshot.updated_at
    session.validation = deepClone(snapshot.validation)
    session.acceptedSnapshot = completeGraph(snapshot.graph)
  }

  function snapshotForSession(id: string): NestedWorkflowSnapshotResponse {
    const session = sessionById(id)
    if (!session) throw new Error(`Sub-workflow session not found: ${id}`)
    return {
      snapshot_version: 1,
      session_id: session.id,
      owner: deepClone(session.owner),
      parent_node_id: session.parentNodeId,
      snapshot_revision: session.snapshotRevision,
      updated_at: session.updatedAt,
      graph: deepClone(session.acceptedSnapshot),
      validation: deepClone(session.validation),
    }
  }

  function closeSession(id: string): void {
    sessions.value = sessions.value.filter((session) => session.id !== id)
  }

  async function deleteDurableSession(id: string): Promise<void> {
    const session = sessionById(id)
    if (!session) return
    if (session.durable) {
      await deleteNestedWorkflowSnapshot(id, session.snapshotRevision)
    }
    closeSession(id)
  }

  return {
    sessions,
    dirtySessionIds,
    sessionById,
    openSession,
    openDurableSession,
    saveSession,
    markSaved,
    updateDraft,
    acceptSnapshot,
    snapshotForSession,
    closeSession,
    deleteDurableSession,
    isDirty,
  }
})
