import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { GraphState } from '@/api/types'

export interface SubWorkflowSession {
  id: string
  parentWorkflowName: string | null
  parentNodeId: string
  parentNodeName: string
  draft: GraphState
  savedSnapshot: GraphState
}

export interface OpenSubWorkflowSessionOptions {
  parentWorkflowName: string | null
  parentNodeId: string
  parentNodeName: string
  graph: GraphState
  readonlyReason?: string | null
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export const useSubWorkflowSessionsStore = defineStore('subWorkflowSessions', () => {
  const sessions = ref<SubWorkflowSession[]>([])

  const dirtySessionIds = computed(() => sessions.value
    .filter((session) => JSON.stringify(session.draft) !== JSON.stringify(session.savedSnapshot))
    .map((session) => session.id))

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
    const session: SubWorkflowSession = {
      id,
      parentWorkflowName: options.parentWorkflowName,
      parentNodeId: options.parentNodeId,
      parentNodeName: options.parentNodeName,
      draft,
      savedSnapshot: deepClone(draft),
    }
    sessions.value = [...sessions.value, session]
    return session
  }

  function isDirty(id: string): boolean {
    const session = sessionById(id)
    if (!session) return false
    return JSON.stringify(session.draft) !== JSON.stringify(session.savedSnapshot)
  }

  function saveSession(id: string): GraphState {
    const session = sessionById(id)
    if (!session) throw new Error(`Sub-workflow session not found: ${id}`)
    session.savedSnapshot = deepClone(session.draft)
    return deepClone(session.draft)
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
