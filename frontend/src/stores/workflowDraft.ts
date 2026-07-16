import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  fetchWorkflowDraft,
  putWorkflowDraft,
  type DraftWriter,
  type WorkflowDraftResponse,
} from '@/api/workflowDrafts'
import type { GraphState } from '@/api/types'

function cloneGraph(graph: GraphState): GraphState {
  return JSON.parse(JSON.stringify(graph)) as GraphState
}

export interface WorkflowDraftChangedMessage {
  type: 'workflow_draft_changed'
  workflow_id: string
  draft_revision: number
  updated_by: DraftWriter
  updated_at: string
  dirty_against_saved: boolean
}

interface RetainedWorkflowDraftState {
  currentDraftRevision: number | null
  appliedDraftRevision: number | null
  remoteAvailableRevision: number | null
  remoteUpdatedBy: DraftWriter | null
  remoteUpdatedAt: string | null
  remoteDirtyAgainstSaved: boolean | null
  lastWriter: string | null
}

function emptyRetainedState(): RetainedWorkflowDraftState {
  return {
    currentDraftRevision: null,
    appliedDraftRevision: null,
    remoteAvailableRevision: null,
    remoteUpdatedBy: null,
    remoteUpdatedAt: null,
    remoteDirtyAgainstSaved: null,
    lastWriter: null,
  }
}

export const useWorkflowDraftStore = defineStore('workflowDraft', () => {
  const retainedByWorkflowId = new Map<string, RetainedWorkflowDraftState>()
  const workflowId = ref<string | null>(null)
  const currentDraftRevision = ref<number | null>(null)
  const appliedDraftRevision = ref<number | null>(null)
  const remoteAvailableRevision = ref<number | null>(null)
  const remoteUpdatedBy = ref<DraftWriter | null>(null)
  const remoteUpdatedAt = ref<string | null>(null)
  const remoteDirtyAgainstSaved = ref<boolean | null>(null)
  const lastWriter = ref<string | null>(null)
  const isStale = computed(() => (
    remoteAvailableRevision.value !== null &&
    appliedDraftRevision.value !== null &&
    remoteAvailableRevision.value > appliedDraftRevision.value
  ))

  function retainedState(id: string): RetainedWorkflowDraftState {
    let state = retainedByWorkflowId.get(id)
    if (state === undefined) {
      state = emptyRetainedState()
      retainedByWorkflowId.set(id, state)
    }
    return state
  }

  function projectState(state: RetainedWorkflowDraftState): void {
    currentDraftRevision.value = state.currentDraftRevision
    appliedDraftRevision.value = state.appliedDraftRevision
    remoteAvailableRevision.value = state.remoteAvailableRevision
    remoteUpdatedBy.value = state.remoteUpdatedBy
    remoteUpdatedAt.value = state.remoteUpdatedAt
    remoteDirtyAgainstSaved.value = state.remoteDirtyAgainstSaved
    lastWriter.value = state.lastWriter
  }

  function projectTrackedWorkflow(id: string): void {
    workflowId.value = id
    projectState(retainedState(id))
  }

  function projectIfTracked(
    id: string,
    state: RetainedWorkflowDraftState,
  ): void {
    if (workflowId.value === id) projectState(state)
  }

  function clearRetainedRemoteChange(state: RetainedWorkflowDraftState): void {
    state.remoteAvailableRevision = null
    state.remoteUpdatedBy = null
    state.remoteUpdatedAt = null
    state.remoteDirtyAgainstSaved = null
  }

  function knownRevision(state: RetainedWorkflowDraftState): number {
    return Math.max(
      state.currentDraftRevision ?? -1,
      state.appliedDraftRevision ?? -1,
      state.remoteAvailableRevision ?? -1,
    )
  }

  function retainRemoteResponse(
    state: RetainedWorkflowDraftState,
    response: WorkflowDraftResponse,
  ): void {
    if (response.draft_revision <= knownRevision(state)) return
    state.remoteAvailableRevision = response.draft_revision
    state.remoteUpdatedBy = response.updated_by
    state.remoteUpdatedAt = response.updated_at
    state.remoteDirtyAgainstSaved = response.dirty_against_saved
  }

  function clearRemoteChange(): void {
    const id = workflowId.value
    if (id === null) {
      remoteAvailableRevision.value = null
      remoteUpdatedBy.value = null
      remoteUpdatedAt.value = null
      remoteDirtyAgainstSaved.value = null
      return
    }
    const state = retainedState(id)
    clearRetainedRemoteChange(state)
    projectState(state)
  }

  async function loadDraft(id: string): Promise<WorkflowDraftResponse> {
    trackWorkflow(id)
    const response = await fetchWorkflowDraft(id)
    acknowledgeAcceptedDraft(response)
    return response
  }

  async function fetchLatestDraft(id: string): Promise<WorkflowDraftResponse> {
    return fetchWorkflowDraft(id)
  }

  async function overwriteDraftWithGraph(
    id: string,
    graph: GraphState,
    _options: { updateTrackedDraft?: boolean } = {},
  ): Promise<WorkflowDraftResponse> {
    const latest = await fetchWorkflowDraft(id)
    const response = await putWorkflowDraft(id, {
      graph: cloneGraph(graph),
      expected_revision: latest.draft_revision,
      updated_by: 'frontend',
    })
    acknowledgeAcceptedDraft(response)
    return response
  }

  function reset(id: string | null = null): void {
    retainedByWorkflowId.clear()
    if (id === null) {
      workflowId.value = null
      projectState(emptyRetainedState())
    } else {
      projectTrackedWorkflow(id)
    }
  }

  function trackWorkflow(id: string): void {
    if (workflowId.value === id) return
    projectTrackedWorkflow(id)
  }

  function forgetWorkflow(id: string): void {
    retainedByWorkflowId.delete(id)
    if (workflowId.value !== id) return
    workflowId.value = null
    projectState(emptyRetainedState())
  }

  function noteRemoteChange(message: WorkflowDraftChangedMessage): void {
    const state = retainedState(message.workflow_id)
    if (message.draft_revision <= knownRevision(state)) return
    state.remoteAvailableRevision = message.draft_revision
    state.remoteUpdatedBy = message.updated_by
    state.remoteUpdatedAt = message.updated_at
    state.remoteDirtyAgainstSaved = message.dirty_against_saved
    projectIfTracked(message.workflow_id, state)
  }

  function acknowledgeAcceptedDraft(response: WorkflowDraftResponse): void {
    const state = retainedState(response.workflow_id)
    const previousAcceptedRevision = Math.max(
      state.currentDraftRevision ?? -1,
      state.appliedDraftRevision ?? -1,
    )
    state.currentDraftRevision = Math.max(
      state.currentDraftRevision ?? -1,
      response.draft_revision,
    )
    state.appliedDraftRevision = Math.max(
      state.appliedDraftRevision ?? -1,
      response.draft_revision,
    )
    if (
      state.remoteAvailableRevision !== null
      && state.remoteAvailableRevision <= response.draft_revision
    ) {
      clearRetainedRemoteChange(state)
    }
    if (response.draft_revision >= previousAcceptedRevision) {
      state.lastWriter = response.updated_by
    }
    projectIfTracked(response.workflow_id, state)
  }

  function hasUnresolvedRemoteChange(id: string | null = workflowId.value): boolean {
    if (!id) return false
    const state = retainedByWorkflowId.get(id)
    if (state === undefined || state.remoteAvailableRevision === null) return false
    return state.appliedDraftRevision === null ||
      state.remoteAvailableRevision > state.appliedDraftRevision
  }

  return {
    workflowId,
    currentDraftRevision,
    appliedDraftRevision,
    remoteAvailableRevision,
    remoteUpdatedBy,
    remoteUpdatedAt,
    remoteDirtyAgainstSaved,
    lastWriter,
    isStale,
    loadDraft,
    fetchLatestDraft,
    overwriteDraftWithGraph,
    reset,
    trackWorkflow,
    forgetWorkflow,
    noteRemoteChange,
    acknowledgeAcceptedDraft,
    clearRemoteChange,
    hasUnresolvedRemoteChange,
  }
})
