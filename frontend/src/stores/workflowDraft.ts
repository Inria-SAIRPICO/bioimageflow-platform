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

export const useWorkflowDraftStore = defineStore('workflowDraft', () => {
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

  function clearRemoteChange(): void {
    remoteAvailableRevision.value = null
    remoteUpdatedBy.value = null
    remoteUpdatedAt.value = null
    remoteDirtyAgainstSaved.value = null
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
    workflowId.value = response.workflow_id
    currentDraftRevision.value = response.draft_revision
    appliedDraftRevision.value = response.draft_revision
    clearRemoteChange()
    lastWriter.value = response.updated_by
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
    workflowId.value = id
    currentDraftRevision.value = null
    appliedDraftRevision.value = null
    clearRemoteChange()
    lastWriter.value = null
    hasQueuedSave.value = false
    isSaving.value = false
  }

  function trackWorkflow(id: string): void {
    if (workflowId.value === id) return
    workflowId.value = id
    currentDraftRevision.value = null
    appliedDraftRevision.value = null
    clearRemoteChange()
    lastWriter.value = null
  }

  function noteRemoteChange(message: WorkflowDraftChangedMessage): void {
    if (workflowId.value !== message.workflow_id) return
    const knownRevision = Math.max(
      currentDraftRevision.value ?? -1,
      appliedDraftRevision.value ?? -1,
      remoteAvailableRevision.value ?? -1,
    )
    if (message.draft_revision <= knownRevision) return
    remoteAvailableRevision.value = message.draft_revision
    remoteUpdatedBy.value = message.updated_by
    remoteUpdatedAt.value = message.updated_at
    remoteDirtyAgainstSaved.value = message.dirty_against_saved
  }

  function acknowledgeAcceptedDraft(response: WorkflowDraftResponse): void {
    if (workflowId.value !== response.workflow_id) return
    currentDraftRevision.value = Math.max(
      currentDraftRevision.value ?? -1,
      response.draft_revision,
    )
    appliedDraftRevision.value = Math.max(
      appliedDraftRevision.value ?? -1,
      response.draft_revision,
    )
    if (
      remoteAvailableRevision.value !== null
      && remoteAvailableRevision.value <= response.draft_revision
    ) {
      clearRemoteChange()
    }
    lastWriter.value = response.updated_by
  }

  function scheduleSave(id: string, graph: GraphState): void {
    if (isStale.value) return
    workflowId.value = id
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
    if (!id || workflowId.value !== id || remoteAvailableRevision.value === null) {
      return false
    }
    return appliedDraftRevision.value === null ||
      remoteAvailableRevision.value > appliedDraftRevision.value
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
        remoteAvailableRevision.value = remote
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
    if (
      appliedDraftRevision.value !== null &&
      latest.draft_revision > appliedDraftRevision.value
    ) {
      remoteAvailableRevision.value = latest.draft_revision
      remoteUpdatedBy.value = latest.updated_by
      remoteUpdatedAt.value = latest.updated_at
      remoteDirtyAgainstSaved.value = latest.dirty_against_saved
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
