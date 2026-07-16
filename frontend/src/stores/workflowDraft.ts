import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { AxiosError } from 'axios'
import {
  fetchWorkflowDraft,
  putWorkflowDraft,
  type DraftWriter,
  type WorkflowDraftResponse,
} from '@/api/workflowDrafts'
import type { GraphState } from '@/api/types'

const DEBOUNCE_MS = 500

let timer: ReturnType<typeof setTimeout> | null = null
let pending: { workflowId: string; graph: GraphState } | null = null

function cloneGraph(graph: GraphState): GraphState {
  return JSON.parse(JSON.stringify(graph)) as GraphState
}

function conflictRevision(err: unknown): number | null {
  if (!(err instanceof AxiosError) || err.response?.status !== 409) return null
  const data = err.response.data as { current_revision?: unknown }
  return typeof data.current_revision === 'number' ? data.current_revision : null
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
  const isSaving = ref(false)
  const hasQueuedSave = ref(false)
  const hasPendingSave = computed(() => hasQueuedSave.value || isSaving.value)
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

  function cancelPendingSave(): void {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    pending = null
    hasQueuedSave.value = false
  }

  function applyResponse(response: WorkflowDraftResponse): void {
    const state = retainedState(response.workflow_id)
    state.currentDraftRevision = response.draft_revision
    state.appliedDraftRevision = response.draft_revision
    clearRetainedRemoteChange(state)
    state.lastWriter = response.updated_by
    projectTrackedWorkflow(response.workflow_id)
  }

  async function loadDraft(id: string): Promise<WorkflowDraftResponse> {
    const response = await fetchWorkflowDraft(id)
    applyResponse(response)
    return response
  }

  async function fetchLatestDraft(id: string): Promise<WorkflowDraftResponse> {
    return fetchWorkflowDraft(id)
  }

  async function overwriteDraftWithGraph(
    id: string,
    graph: GraphState,
    options: { updateTrackedDraft?: boolean } = {},
  ): Promise<WorkflowDraftResponse> {
    const updateTrackedDraft = options.updateTrackedDraft !== false
    if (updateTrackedDraft && workflowId.value === id) {
      cancelPendingSave()
    }
    const latest = await fetchWorkflowDraft(id)
    const response = await putWorkflowDraft(id, {
      graph: cloneGraph(graph),
      expected_revision: latest.draft_revision,
      updated_by: 'frontend',
    })
    if (updateTrackedDraft) {
      applyResponse(response)
    }
    return response
  }

  function reset(id: string | null = null): void {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    pending = null
    retainedByWorkflowId.clear()
    if (id === null) {
      workflowId.value = null
      projectState(emptyRetainedState())
    } else {
      projectTrackedWorkflow(id)
    }
    hasQueuedSave.value = false
    isSaving.value = false
  }

  function trackWorkflow(id: string): void {
    if (workflowId.value === id) return
    projectTrackedWorkflow(id)
  }

  function noteRemoteChange(message: WorkflowDraftChangedMessage): void {
    const state = retainedState(message.workflow_id)
    const knownRevision = Math.max(
      state.currentDraftRevision ?? -1,
      state.appliedDraftRevision ?? -1,
      state.remoteAvailableRevision ?? -1,
    )
    if (message.draft_revision <= knownRevision) return
    state.remoteAvailableRevision = message.draft_revision
    state.remoteUpdatedBy = message.updated_by
    state.remoteUpdatedAt = message.updated_at
    state.remoteDirtyAgainstSaved = message.dirty_against_saved
    projectIfTracked(message.workflow_id, state)
  }

  function acknowledgeAcceptedDraft(response: WorkflowDraftResponse): void {
    const state = retainedState(response.workflow_id)
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
    state.lastWriter = response.updated_by
    projectIfTracked(response.workflow_id, state)
  }

  function scheduleSave(id: string, graph: GraphState): void {
    if (isStale.value) return
    trackWorkflow(id)
    pending = { workflowId: id, graph: cloneGraph(graph) }
    hasQueuedSave.value = true
    if (timer !== null) {
      clearTimeout(timer)
    }
    timer = setTimeout(() => {
      void flush()
    }, DEBOUNCE_MS)
  }

  function hasUnresolvedRemoteChange(id: string | null = workflowId.value): boolean {
    if (!id) return false
    const state = retainedByWorkflowId.get(id)
    if (state === undefined || state.remoteAvailableRevision === null) return false
    return state.appliedDraftRevision === null ||
      state.remoteAvailableRevision > state.appliedDraftRevision
  }

  async function flush(): Promise<void> {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    if (pending === null) {
      hasQueuedSave.value = false
      return
    }
    const entry = pending
    pending = null
    if (currentDraftRevision.value === null || workflowId.value !== entry.workflowId) {
      await loadDraft(entry.workflowId)
    }
    const expected = currentDraftRevision.value ?? 0
    isSaving.value = true
    try {
      const response = await putWorkflowDraft(entry.workflowId, {
        graph: entry.graph,
        expected_revision: expected,
        updated_by: 'frontend',
      })
      applyResponse(response)
    } catch (err) {
      const remote = conflictRevision(err)
      if (remote !== null) {
        const state = retainedState(entry.workflowId)
        state.remoteAvailableRevision = remote
        projectIfTracked(entry.workflowId, state)
      }
      console.warn('[workflow-draft] Failed to save draft:', err)
    } finally {
      isSaving.value = false
      hasQueuedSave.value = pending !== null || timer !== null
    }
  }

  async function ensureFreshForCriticalOperation(
    id: string | null = workflowId.value,
  ): Promise<boolean> {
    await flush()
    if (!id) return true
    if (hasUnresolvedRemoteChange(id)) {
      return false
    }
    const latest = await fetchWorkflowDraft(id)
    const state = retainedState(id)
    if (
      state.appliedDraftRevision !== null &&
      latest.draft_revision > state.appliedDraftRevision
    ) {
      state.remoteAvailableRevision = latest.draft_revision
      state.remoteUpdatedBy = latest.updated_by
      state.remoteUpdatedAt = latest.updated_at
      state.remoteDirtyAgainstSaved = latest.dirty_against_saved
      projectIfTracked(id, state)
      return false
    }
    applyResponse(latest)
    return true
  }

  async function assertFreshForSaveOrRun(): Promise<void> {
    const fresh = await ensureFreshForCriticalOperation()
    if (!fresh) {
      throw new Error('Workflow draft changed outside the canvas. Apply or reload it before continuing.')
    }
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
    isSaving,
    hasPendingSave,
    isStale,
    loadDraft,
    fetchLatestDraft,
    overwriteDraftWithGraph,
    reset,
    trackWorkflow,
    noteRemoteChange,
    acknowledgeAcceptedDraft,
    clearRemoteChange,
    cancelPendingSave,
    scheduleSave,
    hasUnresolvedRemoteChange,
    flush,
    ensureFreshForCriticalOperation,
    assertFreshForSaveOrRun,
  }
})
