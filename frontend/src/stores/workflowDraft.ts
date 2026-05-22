import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { AxiosError } from 'axios'
import { fetchWorkflowDraft, putWorkflowDraft, type WorkflowDraftResponse } from '@/api/workflowDrafts'
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

export const useWorkflowDraftStore = defineStore('workflowDraft', () => {
  const workflowId = ref<string | null>(null)
  const currentDraftRevision = ref<number | null>(null)
  const appliedDraftRevision = ref<number | null>(null)
  const remoteAvailableRevision = ref<number | null>(null)
  const lastWriter = ref<string | null>(null)
  const isSaving = ref(false)
  const isStale = computed(() => (
    remoteAvailableRevision.value !== null &&
    appliedDraftRevision.value !== null &&
    remoteAvailableRevision.value > appliedDraftRevision.value
  ))

  function applyResponse(response: WorkflowDraftResponse): void {
    workflowId.value = response.workflow_id
    currentDraftRevision.value = response.draft_revision
    appliedDraftRevision.value = response.draft_revision
    remoteAvailableRevision.value = null
    lastWriter.value = response.updated_by
  }

  async function loadDraft(id: string): Promise<WorkflowDraftResponse> {
    const response = await fetchWorkflowDraft(id)
    applyResponse(response)
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
    remoteAvailableRevision.value = null
    lastWriter.value = null
    isSaving.value = false
  }

  function scheduleSave(id: string, graph: GraphState): void {
    if (isStale.value) return
    workflowId.value = id
    pending = { workflowId: id, graph: cloneGraph(graph) }
    if (timer !== null) {
      clearTimeout(timer)
    }
    timer = setTimeout(() => {
      void flush()
    }, DEBOUNCE_MS)
  }

  async function flush(): Promise<void> {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    if (pending === null) return
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
    }
  }

  async function assertFreshForSaveOrRun(): Promise<void> {
    const id = workflowId.value
    if (!id) return
    await flush()
    const latest = await fetchWorkflowDraft(id)
    if (
      appliedDraftRevision.value !== null &&
      latest.draft_revision > appliedDraftRevision.value
    ) {
      remoteAvailableRevision.value = latest.draft_revision
      throw new Error('Workflow draft changed outside the canvas. Apply or reload it before continuing.')
    }
    applyResponse(latest)
  }

  return {
    workflowId,
    currentDraftRevision,
    appliedDraftRevision,
    remoteAvailableRevision,
    lastWriter,
    isSaving,
    isStale,
    loadDraft,
    reset,
    scheduleSave,
    flush,
    assertFreshForSaveOrRun,
  }
})
