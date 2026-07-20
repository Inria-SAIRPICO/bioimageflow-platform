import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { makeGraph } from '@/test-utils/graphFixtures'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import { useWorkflowStore } from '@/stores/workflow'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import {
  isRootWorkflowPresentationCurrent,
  loadRootWorkflowPresentation,
} from '../rootWorkflowPresentation'

const autoSaveMocks = vi.hoisted(() => ({
  clearAutoSave: vi.fn().mockResolvedValue(undefined),
  clearAutoSaveStrict: vi.fn().mockResolvedValue(undefined),
  setLastOpenedWorkflow: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/composables/useAutoSave', () => ({
  useAutoSave: () => autoSaveMocks,
}))

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })
  return { promise, resolve, reject }
}

function draftResponse(): WorkflowDraftResponse {
  return {
    draft_version: 1,
    workflow_id: 'race',
    base_saved_revision: 'sha256:saved',
    draft_revision: 2,
    updated_at: '2026-07-16T12:00:00Z',
    updated_by: 'frontend',
    dirty_against_saved: true,
    graph: makeGraph(),
    validation: { valid: true, node_statuses: {}, errors: [] },
  }
}

describe('loadRootWorkflowPresentation identity fencing', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    autoSaveMocks.clearAutoSave.mockClear()
    autoSaveMocks.clearAutoSaveStrict.mockClear()
    autoSaveMocks.setLastOpenedWorkflow.mockClear()
  })

  it('rejects when deletion lands while the retained draft is loading', async () => {
    const workflow = useWorkflowStore()
    const drafts = useWorkflowDraftStore()
    const savedGraph = makeGraph()
    vi.spyOn(workflow, 'loadWorkflow').mockResolvedValue(savedGraph)
    const delayedDraft = deferred<WorkflowDraftResponse>()
    vi.spyOn(drafts, 'loadDraft').mockReturnValueOnce(delayedDraft.promise)

    const opening = loadRootWorkflowPresentation('race')
    await vi.waitFor(() => expect(drafts.loadDraft).toHaveBeenCalledWith('race'))
    await workflow.forgetDeletedWorkflow('race')
    delayedDraft.resolve(draftResponse())

    await expect(opening).rejects.toThrow(/changed identity/i)
  })

  it('marks a resolved graph stale when its workflow generation is later deleted', async () => {
    const workflow = useWorkflowStore()
    const drafts = useWorkflowDraftStore()
    const savedGraph = makeGraph()
    vi.spyOn(workflow, 'loadWorkflow').mockResolvedValue(savedGraph)
    vi.spyOn(drafts, 'loadDraft').mockRejectedValueOnce(new Error('no draft'))

    const presentation = await loadRootWorkflowPresentation('race')

    expect(isRootWorkflowPresentationCurrent(
      'race',
      presentation.graph,
      presentation.identityGeneration,
    )).toBe(true)
    await workflow.forgetDeletedWorkflow('race')
    expect(isRootWorkflowPresentationCurrent(
      'race',
      presentation.graph,
      presentation.identityGeneration,
    )).toBe(false)
  })
})
