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
  ValidationResult,
} from '@/api/types'
import { graphDocumentsEqual } from '@/sessions/graphDocument'

export type NestedWorkflowParentConflictReason = 'parent_missing' | 'parent_changed'

export interface NestedWorkflowSession {
  id: string
  owner: NestedSnapshotOwner
  parentCanvasId: string
  parentWorkflowName: string | null
  parentSourceWorkflowName: string | null
  parentNodeId: string
  parentNodeName: string
  draft: GraphState
  /** Child document last applied to the parent node. */
  savedSnapshot: GraphState
  acceptedSnapshot: GraphState
  parentApplyConflict: NestedWorkflowParentConflictReason | null
  snapshotRevision: number
  updatedAt: string
  validation: ValidationResult
}

export interface OpenDurableNestedWorkflowSessionOptions {
  owner: NestedSnapshotOwner
  parentCanvasId: string
  parentWorkflowName: string | null
  parentSourceWorkflowName?: string | null
  parentNodeId: string
  parentNodeName: string
  graph: GraphState
}

export interface OpenDurableNestedWorkflowSessionResult {
  session: NestedWorkflowSession
  created: boolean
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function completeGraph(graph: GraphState): GraphState {
  return deepClone(graph)
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
  options: OpenDurableNestedWorkflowSessionOptions,
  snapshot: NestedWorkflowSnapshotResponse,
  draft: GraphState,
  savedSnapshot: GraphState,
): NestedWorkflowSession {
  const session = {
    id: snapshot.session_id,
    owner: snapshot.owner,
    parentCanvasId: options.parentCanvasId,
    parentWorkflowName: options.parentWorkflowName,
    parentSourceWorkflowName: options.parentSourceWorkflowName ?? null,
    parentNodeId: options.parentNodeId,
    parentNodeName: options.parentNodeName,
    draft,
    savedSnapshot,
    acceptedSnapshot: deepClone(draft),
    parentApplyConflict: null,
    snapshotRevision: snapshot.snapshot_revision,
    updatedAt: snapshot.updated_at,
    validation: deepClone(snapshot.validation),
  } satisfies NestedWorkflowSession
  return session
}

export const useNestedWorkflowSessionsStore = defineStore('nestedWorkflowSessions', () => {
  const sessions = ref<NestedWorkflowSession[]>([])

  const dirtySessionIds = computed(() => sessions.value
    .filter((session) => isSessionDirty(session))
    .map((session) => session.id))

  function isSessionDirty(session: NestedWorkflowSession): boolean {
    return session.parentApplyConflict !== null
      || !graphDocumentsEqual(session.draft, session.savedSnapshot)
  }

  function sessionById(id: string): NestedWorkflowSession | undefined {
    return sessions.value.find((session) => session.id === id)
  }

  async function openDurableSession(
    options: OpenDurableNestedWorkflowSessionOptions,
  ): Promise<NestedWorkflowSession> {
    return (await openDurableSessionResult(options)).session
  }

  async function openDurableSessionResult(
    options: OpenDurableNestedWorkflowSessionOptions,
  ): Promise<OpenDurableNestedWorkflowSessionResult> {
    const existing = sessions.value.find(session => (
      session.parentNodeId === options.parentNodeId
      && sameOwner(session.owner, options.owner)
    ))
    if (existing) return { session: existing, created: false }

    const parentBaseline = completeGraph(options.graph)
    const snapshot = await openNestedWorkflowSnapshot({
      owner: options.owner,
      parent_node_id: options.parentNodeId,
      graph: parentBaseline,
    })
    const concurrentlyOpened = sessionById(snapshot.session_id)
    if (concurrentlyOpened) {
      return { session: concurrentlyOpened, created: false }
    }
    const session = createSession(
      options,
      snapshot,
      completeGraph(snapshot.graph),
      parentBaseline,
    )
    sessions.value = [...sessions.value, session]
    return { session: sessionById(session.id)!, created: true }
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
    if (!session) throw new Error(`nested-workflow session not found: ${id}`)
    const accepted = completeGraph(graph)
    session.draft = deepClone(accepted)
    session.savedSnapshot = deepClone(accepted)
    session.parentApplyConflict = null
    if (snapshotRevision !== null && snapshotRevision !== undefined) {
      session.snapshotRevision = snapshotRevision
    }
    if (validation) session.validation = deepClone(validation)
    session.acceptedSnapshot = deepClone(accepted)
  }

  function updateDraft(id: string, graph: GraphState): void {
    const session = sessionById(id)
    if (!session) throw new Error(`nested-workflow session not found: ${id}`)
    session.draft = completeGraph(graph)
  }

  function markParentApplyConflict(
    id: string,
    reason: NestedWorkflowParentConflictReason,
  ): void {
    const session = sessionById(id)
    if (!session) throw new Error(`nested-workflow session not found: ${id}`)
    session.parentApplyConflict = reason
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
    if (!session) throw new Error(`nested-workflow session not found: ${id}`)
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
    await deleteNestedWorkflowSnapshot(id, session.snapshotRevision)
    closeSession(id)
  }

  return {
    sessions,
    dirtySessionIds,
    sessionById,
    openDurableSession,
    openDurableSessionResult,
    markSaved,
    updateDraft,
    markParentApplyConflict,
    acceptSnapshot,
    snapshotForSession,
    closeSession,
    deleteDurableSession,
    isDirty,
  }
})
