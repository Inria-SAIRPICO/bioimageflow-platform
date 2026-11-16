import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { makeGraph } from '@/test-utils/graphFixtures'
import { api } from '@/api/client'
import { canvasIdFromPanelId, canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { useUIStore } from '@/stores/ui'
import type { WorkflowInfo, WorkflowFile } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import { useWorkflowStore } from '@/stores/workflow'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import { useSettingsStore } from '@/stores/settings'
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
  afterEach(() => { vi.restoreAllMocks(); canvasSessionRegistry.dispose() })
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    autoSaveMocks.clearAutoSave.mockClear()
    autoSaveMocks.clearAutoSaveStrict.mockClear()
    autoSaveMocks.setLastOpenedWorkflow.mockClear()
  })

  it('accepted background startup still restores workflow dependency diagnostics', async () => {
    const diagnostic = { node_id: 'seed', tool_name: 'missing-tool' }
    const missingPackage = { package_name: 'missing-package', required_version: '1.0' }
    vi.spyOn(api, 'get').mockImplementation(async url => ({ data: url.includes('workflow-drafts')
      ? draftResponse()
      : { info: { name: 'race', display_name: 'Race' }, graph: makeGraph(),
        missing_tools: [diagnostic], missing_packages: [missingPackage] },
    }))
    const loaded = await loadRootWorkflowPresentation('race', { background: true, canPresent: () => true })
    expect(loaded.missingTools).toEqual([diagnostic])
    expect(useWorkflowStore().missingPackages).toEqual([missingPackage])
    expect(useWorkflowStore().currentName).toBe('race')
  })

  it.each(['saved', 'draft'])('late background %s loading leaves the active child and dirty root intact', async (heldPhase) => {
    const workflow = useWorkflowStore()
    const drafts = useWorkflowDraftStore()
    const ui = useUIStore()
    const info = { name: 'race', display_name: 'Race', identity_generation: 1 } as WorkflowInfo
    const saved = deferred<{ data: WorkflowFile }>()
    const draft = deferred<{ data: WorkflowDraftResponse }>()
    const savedResponse = { data: { info, graph: makeGraph(), artifact_hash: "sha256:saved", missing_tools: [], missing_packages: [] } }
    const get = vi.spyOn(api, 'get').mockImplementation((url) => (
      url.includes('workflow-drafts') ? draft.promise : saved.promise
    ))
    if (heldPhase === 'draft') saved.resolve(savedResponse)
    let canPresent = true
    const opening = loadRootWorkflowPresentation('race', { background: true, canPresent: () => canPresent })
    if (heldPhase === 'draft') await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(2))

    canPresent = false
    // A winning explicit Open now owns a different root and an inspected child.
    const rootId = canvasIdFromPanelId('workflow:race')
    const childId = canvasIdFromPanelId('nested-workflow:child')
    canvasSessionRegistry.register({ kind: 'root', canvasId: rootId, workflowId: 'race' })
    canvasSessionRegistry.register({ kind: 'nested', canvasId: childId, sessionId: 'child', parentCanvasId: rootId })
    canvasSessionRegistry.activate(childId)
    ui.markCanvasDirty(rootId)
    ui.setCanvasSelectedNodes(childId, ['increment'])
    workflow.current = { name: 'other', display_name: 'Other' } as WorkflowInfo
    drafts.acknowledgeAcceptedDraft({ ...draftResponse(), workflow_id: 'other', draft_revision: 7 })
    drafts.trackWorkflow('other')
    saved.resolve(savedResponse)
    draft.resolve({ data: draftResponse() })
    await expect(opening).resolves.toMatchObject({ workflowName: 'race', draft: { draft_revision: 2 } })
    expect(workflow.currentName).toBe('other')
    expect(ui.canvasHasUnsavedChanges(rootId)).toBe(true)
    expect(canvasSessionRegistry.activeCanvasId.value).toBe(childId)
    expect(ui.selectedNodeIds).toEqual(['increment'])
    expect(drafts.workflowId).toBe('other')
    expect(drafts.appliedDraftRevision).toBe(7)
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

  it.each([true, false])('binds %s background draft loading to its saved workspace and rejects a switched response', async background => {
    const workflow = useWorkflowStore()
    const draft = deferred<{ data: WorkflowDraftResponse }>()
    const info = { id: 'race', name: 'race', display_name: 'Race', workspace_path: '/workspace/A', identity_generation: 0 } as WorkflowInfo
    workflow.workflows = [info]
    useSettingsStore().settings = { workspace_path: '/workspace/A' } as any
    const get = vi.spyOn(api, 'get').mockImplementation(async url => url.includes('workflow-drafts')
      ? await draft.promise
      : { data: { info, graph: makeGraph(), missing_tools: [], missing_packages: [] } })
    const opening = loadRootWorkflowPresentation('race', { background })
    await vi.waitFor(() => expect(get).toHaveBeenCalledWith('/api/v1/workflow-drafts/race', {
      headers: { 'X-BioImageFlow-Workspace': '/workspace/A' },
    }))
    useSettingsStore().workspaceSelectionRevision += 1
    useSettingsStore().settings = { workspace_path: '/workspace/B' } as any
    draft.resolve({ data: draftResponse() })
    await expect(opening).rejects.toThrow('workspace changed')
    expect(useWorkflowDraftStore().appliedDraftRevision).toBeNull()
  })

  it('marks an accepted presentation stale after selecting a copied workspace', async () => {
    const workflow = useWorkflowStore()
    vi.spyOn(workflow, 'loadWorkflow').mockResolvedValue(makeGraph())
    vi.spyOn(useWorkflowDraftStore(), 'loadDraft').mockResolvedValueOnce(draftResponse())
    const accepted = await loadRootWorkflowPresentation('race')
    useSettingsStore().workspaceSelectionRevision += 1
    expect(isRootWorkflowPresentationCurrent('race', accepted.graph, accepted.identityGeneration)).toBe(false)
  })
})
