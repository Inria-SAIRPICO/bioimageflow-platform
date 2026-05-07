import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { GraphState, PublishedInput, PublishedOutput } from '@/api/types'

export interface SubWorkflowSession {
  id: string
  parentWorkflowName: string | null
  parentNodeId: string
  parentNodeName: string
  draft: GraphState
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
      parentWorkflowName: options.parentWorkflowName,
      parentNodeId: options.parentNodeId,
      parentNodeName: options.parentNodeName,
      draft,
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
    closeSession,
    isDirty,
  }
})
