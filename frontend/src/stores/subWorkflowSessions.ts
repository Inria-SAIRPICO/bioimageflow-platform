import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  GraphState,
  PublishedInput,
  PublishedOutput,
  ValidationResult,
} from '@/api/types'

export interface SubWorkflowSession {
  id: string
  draft_id: string
  revision: number
  client_seq: number
  parentWorkflowName: string | null
  parentNodeId: string
  parentNodeName: string
  draft: GraphState
  validation_result: ValidationResult | null
  dirty: boolean
  pending_sync: boolean
  savedSnapshot: GraphState
  published_inputs: PublishedInput[]
  published_outputs: PublishedOutput[]
  savedPublishedInputs: PublishedInput[]
  savedPublishedOutputs: PublishedOutput[]
}

export interface OpenSubWorkflowSessionOptions {
  parentWorkflowName: string | null
  parentNodeId: string
  parentNodeName: string
  graph: GraphState
  published_inputs?: PublishedInput[]
  published_outputs?: PublishedOutput[]
  readonlyReason?: string | null
}

export interface SavedSubWorkflowSession {
  graph: GraphState
  published_inputs: PublishedInput[]
  published_outputs: PublishedOutput[]
}

export interface SubWorkflowDraftSyncState {
  revision?: number
  client_seq?: number
  validation_result?: ValidationResult | null
  dirty?: boolean
  pending_sync?: boolean
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export const useSubWorkflowSessionsStore = defineStore('subWorkflowSessions', () => {
  const sessions = ref<SubWorkflowSession[]>([])

  const dirtySessionIds = computed(() => sessions.value
    .filter((session) => isSessionDirty(session))
    .map((session) => session.id))

  function isSessionDirty(session: SubWorkflowSession): boolean {
    return JSON.stringify({
      graph: session.draft,
      published_inputs: session.published_inputs,
      published_outputs: session.published_outputs,
    }) !== JSON.stringify({
      graph: session.savedSnapshot,
      published_inputs: session.savedPublishedInputs,
      published_outputs: session.savedPublishedOutputs,
    })
  }

  function sessionId(parentWorkflowName: string | null, parentNodeId: string): string {
    return `${parentWorkflowName ?? '__unsaved__'}:${parentNodeId}`
  }

  function draftIdForSession(id: string): string {
    return `sub-workflow:${id}`
  }

  function sessionById(id: string): SubWorkflowSession | undefined {
    return sessions.value.find((session) => session.id === id)
  }

  function openSession(options: OpenSubWorkflowSessionOptions): SubWorkflowSession {
    if (options.readonlyReason) {
      throw new Error(options.readonlyReason)
    }
    const id = sessionId(options.parentWorkflowName, options.parentNodeId)
    const existing = sessionById(id)
    if (existing) return existing

    const draft = deepClone(options.graph)
    const publishedInputs = deepClone(options.published_inputs ?? [])
    const publishedOutputs = deepClone(options.published_outputs ?? [])
    const session: SubWorkflowSession = {
      id,
      draft_id: draftIdForSession(id),
      revision: 0,
      client_seq: 0,
      parentWorkflowName: options.parentWorkflowName,
      parentNodeId: options.parentNodeId,
      parentNodeName: options.parentNodeName,
      draft,
      validation_result: null,
      dirty: false,
      pending_sync: false,
      savedSnapshot: deepClone(draft),
      published_inputs: publishedInputs,
      published_outputs: publishedOutputs,
      savedPublishedInputs: deepClone(publishedInputs),
      savedPublishedOutputs: deepClone(publishedOutputs),
    }
    sessions.value = [...sessions.value, session]
    return session
  }

  function isDirty(id: string): boolean {
    const session = sessionById(id)
    if (!session) return false
    return isSessionDirty(session)
  }

  function saveSession(id: string): SavedSubWorkflowSession {
    const session = sessionById(id)
    if (!session) throw new Error(`Sub-workflow session not found: ${id}`)
    session.savedSnapshot = deepClone(session.draft)
    session.savedPublishedInputs = deepClone(session.published_inputs)
    session.savedPublishedOutputs = deepClone(session.published_outputs)
    session.dirty = false
    return {
      graph: deepClone(session.draft),
      published_inputs: deepClone(session.published_inputs),
      published_outputs: deepClone(session.published_outputs),
    }
  }

  function updateDraft(id: string, graph: GraphState): void {
    const session = sessionById(id)
    if (!session) throw new Error(`Sub-workflow session not found: ${id}`)
    session.draft = deepClone(graph)
    session.dirty = true
  }

  function updateDraftSyncState(id: string, state: SubWorkflowDraftSyncState): void {
    const session = sessionById(id)
    if (!session) throw new Error(`Sub-workflow session not found: ${id}`)
    if (state.revision !== undefined) session.revision = state.revision
    if (state.client_seq !== undefined) session.client_seq = state.client_seq
    if (state.validation_result !== undefined) {
      session.validation_result = state.validation_result
    }
    if (state.dirty !== undefined) session.dirty = state.dirty
    if (state.pending_sync !== undefined) session.pending_sync = state.pending_sync
  }

  function closeSession(id: string): void {
    sessions.value = sessions.value.filter((session) => session.id !== id)
  }

  return {
    sessions,
    dirtySessionIds,
    sessionById,
    openSession,
    saveSession,
    updateDraft,
    updateDraftSyncState,
    closeSession,
    isDirty,
  }
})
