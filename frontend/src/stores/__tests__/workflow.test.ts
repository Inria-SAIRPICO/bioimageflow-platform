import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError } from 'axios'

const autoSaveMocks = vi.hoisted(() => ({
  clearAutoSave: vi.fn().mockResolvedValue(undefined),
  clearAutoSaveStrict: vi.fn().mockResolvedValue(undefined),
  setLastOpenedWorkflow: vi.fn().mockResolvedValue(undefined),
  renameWorkflow: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/composables/useAutoSave', () => ({
  useAutoSave: () => autoSaveMocks,
}))

import { api } from '@/api/client'
import { useWorkflowStore } from '../workflow'
import { useWorkflowDraftStore } from '../workflowDraft'
import { useUIStore } from '../ui'
import type { WorkflowInfo } from '@/api/types'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })
  return { promise, resolve, reject }
}

function workflowInfo(id: string, displayName = id): WorkflowInfo {
  const leaf = id.slice(id.lastIndexOf('/') + 1)
  const folder = id.includes('/') ? id.slice(0, id.lastIndexOf('/')) : ''
  return {
    id,
    name: leaf,
    folder,
    display_name: displayName,
    path: `/tmp/${id}/workflow.json`,
    last_modified: '2026-07-16T10:00:00Z',
  }
}

function registerWorkflowCanvas(
  workflowId: string,
  kind: 'root' | 'nested' = 'root',
): CanvasId {
  const canvasId = canvasIdFromPanelId(`${kind}:${workflowId}`)
  if (kind === 'root') {
    canvasSessionRegistry.register({ kind, canvasId, workflowId })
  } else {
    canvasSessionRegistry.register({
      kind,
      canvasId,
      sessionId: `session:${workflowId}`,
      parentCanvasId: canvasIdFromPanelId(`parent:${workflowId}`),
    })
  }
  useUIStore().setCanvasWorkflow(canvasId, workflowId, workflowId)
  return canvasId
}

function noteRemoteDraft(workflowId: string, revision: number): void {
  useWorkflowDraftStore().noteRemoteChange({
    type: 'workflow_draft_changed',
    workflow_id: workflowId,
    draft_revision: revision,
    updated_by: 'agent',
    updated_at: '2026-07-16T10:05:00Z',
    dirty_against_saved: true,
  })
}

describe('workflow store', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.patch).mockReset()
    vi.mocked(api.post).mockReset()
    vi.mocked(api.put).mockReset()
    vi.mocked(api.delete).mockReset()
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    })
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    })
    autoSaveMocks.clearAutoSave.mockClear()
    autoSaveMocks.clearAutoSaveStrict.mockReset().mockResolvedValue(undefined)
    autoSaveMocks.setLastOpenedWorkflow.mockClear()
    autoSaveMocks.renameWorkflow.mockClear()
  })

  it('forgets retained draft state after deleting a workflow', async () => {
    vi.mocked(api.delete).mockResolvedValueOnce({ data: { deleted: true } })
    const store = useWorkflowStore()
    store.workflows = [{
      name: 'workflow-b',
      display_name: 'Workflow B',
      path: '/tmp/workflow-b.json',
      last_modified: '2026-07-16T10:00:00Z',
    }]
    const drafts = useWorkflowDraftStore()
    drafts.reset('workflow-a')
    noteRemoteDraft('workflow-b', 6)

    await store.deleteWorkflow('workflow-b')
    drafts.trackWorkflow('workflow-b')

    expect(drafts.currentDraftRevision).toBeNull()
    expect(drafts.appliedDraftRevision).toBeNull()
    expect(drafts.remoteAvailableRevision).toBeNull()
  })

  it('rejects a delayed open after the workflow is removed remotely', async () => {
    const response = deferred<any>()
    vi.mocked(api.get).mockReturnValueOnce(response.promise)
    const store = useWorkflowStore()

    const opening = store.loadWorkflow('race')
    await store.forgetDeletedWorkflow('race')
    response.resolve({
      data: {
        info: workflowInfo('race', 'Stale generation'),
        graph: { nodes: [{ id: 'stale' }], edges: [] },
        missing_packages: [],
        missing_tools: [],
      },
    })

    await expect(opening).rejects.toThrow(/changed identity/i)
    expect(store.workflows).toEqual([])
    expect(store.current).toBeNull()
    expect(autoSaveMocks.setLastOpenedWorkflow).not.toHaveBeenCalledWith('race')
  })

  it('suppresses opens while local deletion is in flight', async () => {
    const loadResponse = deferred<any>()
    const deleteResponse = deferred<any>()
    vi.mocked(api.get).mockReturnValueOnce(loadResponse.promise)
    vi.mocked(api.delete).mockReturnValueOnce(deleteResponse.promise)
    const store = useWorkflowStore()

    const opening = store.loadWorkflow('race')
    const deletion = store.deleteWorkflow('race')

    expect(store.isWorkflowDeletionInFlight('race')).toBe(true)
    await expect(store.loadWorkflow('race')).rejects.toThrow(/changed identity/i)
    expect(api.get).toHaveBeenCalledOnce()

    loadResponse.resolve({
      data: {
        info: workflowInfo('race', 'Stale generation'),
        graph: { nodes: [{ id: 'stale' }], edges: [] },
        missing_packages: [],
        missing_tools: [],
      },
    })
    await expect(opening).rejects.toThrow(/changed identity/i)

    deleteResponse.resolve({ data: { deleted: true } })
    await deletion
    expect(store.isWorkflowDeletionInFlight('race')).toBe(false)
    expect(store.workflows).toEqual([])
  })

  it('does not forget a newer remote recreation when an older delete response arrives late', async () => {
    const deleteResponse = deferred<any>()
    vi.mocked(api.delete).mockReturnValueOnce(deleteResponse.promise)
    const store = useWorkflowStore()
    store.workflows = [{
      ...workflowInfo('race', 'Deleted generation'),
      identity_generation: 10,
    } as WorkflowInfo]

    const deletion = store.deleteWorkflow('race')
    vi.mocked(api.get).mockResolvedValueOnce({
      data: [{
        ...workflowInfo('race', 'Fresh generation'),
        identity_generation: 12,
      }],
    })
    await store.fetchWorkflows()
    const localIdentityGeneration = store.workflowIdentityGeneration('race')
    deleteResponse.resolve({
      data: { deleted: true, identity_generation: 11 },
    })

    await expect(deletion).rejects.toThrow(/changed identity/i)
    expect(store.workflowIdentityGeneration('race')).toBeGreaterThan(
      localIdentityGeneration,
    )
    expect(store.workflows).toHaveLength(1)
    expect(store.workflows[0]?.display_name).toBe('Fresh generation')
    expect(store.isWorkflowDeletionInFlight('race')).toBe(false)
    expect(autoSaveMocks.clearAutoSaveStrict).not.toHaveBeenCalled()
  })

  it('allows an explicit same-id creation as a fresh generation without accepting an older open', async () => {
    const oldResponse = deferred<any>()
    vi.mocked(api.get).mockReturnValueOnce(oldResponse.promise)
    const store = useWorkflowStore()
    const oldOpening = store.loadWorkflow('race')

    vi.mocked(api.delete).mockResolvedValueOnce({ data: { deleted: true } })
    await store.deleteWorkflow('race')
    vi.mocked(api.post).mockResolvedValueOnce({
      data: workflowInfo('race', 'Fresh generation'),
    })
    await store.createWorkflow({
      name: 'race',
      display_name: 'Fresh generation',
      description: null,
    })

    oldResponse.resolve({
      data: {
        info: workflowInfo('race', 'Stale generation'),
        graph: { nodes: [{ id: 'stale' }], edges: [] },
        missing_packages: [],
        missing_tools: [],
      },
    })

    await expect(oldOpening).rejects.toThrow(/changed identity/i)
    expect(store.workflows).toHaveLength(1)
    expect(store.workflows[0]?.display_name).toBe('Fresh generation')

    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        info: workflowInfo('race', 'Fresh generation'),
        graph: { nodes: [{ id: 'fresh' }], edges: [] },
        missing_packages: [],
        missing_tools: [],
      },
    })
    await expect(store.loadWorkflow('race')).resolves.toEqual({
      nodes: [{ id: 'fresh' }],
      edges: [],
    })
  })

  it('holds the deletion fence until delayed recovery cleanup finishes', async () => {
    const cleanup = deferred<void>()
    autoSaveMocks.clearAutoSaveStrict.mockReturnValueOnce(cleanup.promise)
    const store = useWorkflowStore()
    store.workflows = [workflowInfo('race', 'Deleted generation')]
    store.current = store.workflows[0]!

    const forgetting = store.forgetDeletedWorkflow('race')

    expect(store.current).toBeNull()
    expect(store.workflows).toEqual([])
    expect(store.isWorkflowDeletionInFlight('race')).toBe(true)
    await expect(store.createWorkflow({
      name: 'race',
      display_name: 'Too early',
      description: null,
    })).rejects.toThrow(/changed identity/i)
    expect(api.post).not.toHaveBeenCalled()

    cleanup.resolve()
    await forgetting
    expect(store.isWorkflowDeletionInFlight('race')).toBe(false)

    vi.mocked(api.post).mockResolvedValueOnce({
      data: workflowInfo('race', 'Fresh generation'),
    })
    await expect(store.createWorkflow({
      name: 'race',
      display_name: 'Fresh generation',
      description: null,
    })).resolves.toMatchObject({ display_name: 'Fresh generation' })
  })

  it('keeps a committed deletion converged when local recovery cleanup fails', async () => {
    vi.mocked(api.delete).mockResolvedValueOnce({ data: { deleted: true } })
    autoSaveMocks.clearAutoSaveStrict.mockRejectedValueOnce(new Error('IndexedDB unavailable'))
    const store = useWorkflowStore()
    store.workflows = [workflowInfo('race', 'Deleted generation')]
    store.current = store.workflows[0]!

    await expect(store.deleteWorkflow('race'))
      .rejects.toThrow(/local recovery cleanup failed/i)

    expect(store.current).toBeNull()
    expect(store.workflows).toEqual([])
    expect(store.isWorkflowDeletionInFlight('race')).toBe(false)
    expect(store.error).toContain('local recovery cleanup failed')
  })

  it('passes the captured durable identity generation to DELETE', async () => {
    vi.mocked(api.delete).mockResolvedValueOnce({
      data: { deleted: true, identity_generation: 8 },
    })
    const store = useWorkflowStore()
    store.workflows = [workflowInfo('race', 'Generation 7')]
    store.observeWorkflowServerIdentityGeneration('race', 7)

    await store.deleteWorkflow('race', { expectedIdentityGeneration: 7 })

    expect(api.delete).toHaveBeenCalledWith('/api/v1/workflows/race', {
      params: { expected_identity_generation: 7 },
    })
  })

  it('does not advance the local identity generation when DELETE fails', async () => {
    const failure = new Error('backend unavailable')
    vi.mocked(api.delete).mockRejectedValueOnce(failure)
    const store = useWorkflowStore()
    store.workflows = [workflowInfo('race', 'Generation 7')]
    store.observeWorkflowServerIdentityGeneration('race', 7)
    const localIdentityGeneration = store.workflowIdentityGeneration('race')

    await expect(store.deleteWorkflow('race', {
      expectedIdentityGeneration: 7,
    })).rejects.toBe(failure)

    expect(store.workflowIdentityGeneration('race')).toBe(localIdentityGeneration)
    expect(store.workflowServerIdentityGeneration('race')).toBe(7)
    expect(store.isWorkflowDeletionInFlight('race')).toBe(false)
    expect(store.workflows).toHaveLength(1)
  })

  it('rejects generation replacement when old recovery cleanup fails', async () => {
    autoSaveMocks.clearAutoSaveStrict.mockRejectedValueOnce(new Error('IndexedDB unavailable'))
    const store = useWorkflowStore()
    store.workflows = [workflowInfo('race', 'Fresh generation')]
    store.current = store.workflows[0]!

    await expect(store.resetWorkflowPresentationGeneration('race'))
      .rejects.toThrow(/local recovery cleanup failed/i)

    expect(store.workflows).toHaveLength(1)
    expect(store.current).toBeNull()
    expect(store.isWorkflowDeletionInFlight('race')).toBe(false)
  })

  it('finishes a delayed save against its original canvas without claiming it is clean', async () => {
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'a' })
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'b' })
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
    ui.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
    ui.markCanvasDirty(canvasA)
    ui.markCanvasDirty(canvasB)

    const workflowA = {
      name: 'a',
      display_name: 'Workflow A',
      path: '/tmp/a.json',
      last_modified: '2026-07-15T10:00:00Z',
    } as WorkflowInfo
    const workflowB = {
      name: 'b',
      display_name: 'Workflow B',
      path: '/tmp/b.json',
      last_modified: '2026-07-15T10:00:00Z',
    } as WorkflowInfo
    const store = useWorkflowStore()
    store.workflows = [workflowA, workflowB]
    store.current = workflowA
    canvasSessionRegistry.activate(canvasA)

    let resolveSave!: (value: { data: WorkflowInfo }) => void
    vi.mocked(api.put).mockReturnValueOnce(new Promise((resolve) => {
      resolveSave = resolve
    }))
    const save = store.saveWorkflow(
      { nodes: [], edges: [] },
      { canvasId: canvasA, workflowName: 'a' },
    )

    canvasSessionRegistry.activate(canvasB)
    store.current = workflowB
    resolveSave({
      data: {
        ...workflowA,
        display_name: 'Workflow A saved',
        last_modified: '2026-07-15T10:01:00Z',
      },
    })
    await save

    expect(store.currentName).toBe('b')
    expect(ui.activeWorkflowId).toBe('b')
    expect(ui.activeWorkflowName).toBe('Workflow B')
    expect(ui.hasUnsavedChanges).toBe(true)
    expect(ui.canvasHasUnsavedChanges(canvasA)).toBe(true)
  })

  it('rejects a delayed save response after remote deletion without relisting the workflow', async () => {
    const saveResponse = deferred<any>()
    vi.mocked(api.put).mockReturnValueOnce(saveResponse.promise)
    const store = useWorkflowStore()
    store.workflows = [workflowInfo('race', 'Deleted generation')]

    const saving = store.saveWorkflow(
      { nodes: [], edges: [] },
      {
        canvasId: canvasIdFromPanelId('workflow:race'),
        workflowName: 'race',
      },
    )
    await store.forgetDeletedWorkflow('race')
    saveResponse.resolve({ data: workflowInfo('race', 'Stale save response') })

    await expect(saving).rejects.toThrow(/changed identity/i)
    expect(store.workflows).toEqual([])
  })

  it('rejects a delayed creation after that new identity is removed remotely', async () => {
    const createResponse = deferred<any>()
    vi.mocked(api.post).mockReturnValueOnce(createResponse.promise)
    const store = useWorkflowStore()

    const creating = store.createWorkflow({
      name: 'race',
      display_name: 'Race',
      description: null,
    })
    await store.forgetDeletedWorkflow('race')
    createResponse.resolve({ data: workflowInfo('race', 'Stale creation') })

    await expect(creating).rejects.toThrow(/changed identity/i)
    expect(store.workflows).toEqual([])
    expect(store.current).toBeNull()
    expect(autoSaveMocks.setLastOpenedWorkflow).not.toHaveBeenCalledWith('race')
  })

  it('rejects a delayed import after its destination identity is removed remotely', async () => {
    const importResponse = deferred<any>()
    vi.mocked(api.post).mockReturnValueOnce(importResponse.promise)
    const store = useWorkflowStore()
    const file = new File(['zip'], 'race.bioimageflow.zip', { type: 'application/zip' })

    const importing = store.importWorkflow(file)
    await store.forgetDeletedWorkflow('race')
    importResponse.resolve({
      data: {
        info: workflowInfo('race', 'Stale import'),
        missing_packages: [{ package_name: 'stale' }],
        missing_tools: [{ node_id: 'stale', tool_name: 'Stale' }],
      },
    })

    await expect(importing).rejects.toThrow(/changed identity/i)
    expect(store.workflows).toEqual([])
    expect(store.missingPackages).toEqual([])
    expect(store.missingTools).toEqual([])
  })

  it('rejects a delayed metadata update after its source is removed remotely', async () => {
    const patchResponse = deferred<any>()
    vi.mocked(api.patch).mockReturnValueOnce(patchResponse.promise)
    const store = useWorkflowStore()
    store.workflows = [workflowInfo('race', 'Original')]

    const patching = store.patchWorkflow('race', {
      action: 'update',
      display_name: 'Stale update',
    })
    await store.forgetDeletedWorkflow('race')
    patchResponse.resolve({ data: workflowInfo('race', 'Stale update') })

    await expect(patching).rejects.toThrow(/changed identity/i)
    expect(store.workflows).toEqual([])
  })

  it('rejects a delayed rename after its destination is removed remotely', async () => {
    const patchResponse = deferred<any>()
    vi.mocked(api.patch).mockReturnValueOnce(patchResponse.promise)
    const store = useWorkflowStore()
    store.workflows = [workflowInfo('source', 'Source')]

    const renaming = store.patchWorkflow('source', {
      action: 'update',
      new_id: 'destination',
    })
    await store.forgetDeletedWorkflow('destination')
    patchResponse.resolve({ data: workflowInfo('destination', 'Stale destination') })

    await expect(renaming).rejects.toThrow(/changed identity/i)
    expect(store.workflows.map(item => item.id)).toEqual(['source'])
    expect(autoSaveMocks.renameWorkflow).not.toHaveBeenCalled()
  })

  it.each(['source', 'copy'])(
    'rejects a delayed duplicate after its %s identity is removed remotely',
    async (removedIdentity) => {
      const patchResponse = deferred<any>()
      vi.mocked(api.patch).mockReturnValueOnce(patchResponse.promise)
      const store = useWorkflowStore()
      store.workflows = [workflowInfo('source', 'Source')]

      const duplicating = store.patchWorkflow('source', {
        action: 'duplicate',
        new_name: 'copy',
        display_name: 'Copy',
      })
      await store.forgetDeletedWorkflow(removedIdentity)
      patchResponse.resolve({ data: workflowInfo('copy', 'Stale copy') })

      await expect(duplicating).rejects.toThrow(/changed identity/i)
      expect(store.workflows.some(item => item.id === 'copy')).toBe(false)
    },
  )

  it('rejects a delayed rebind after its workflow is removed remotely', async () => {
    const rebindResponse = deferred<any>()
    vi.mocked(api.post).mockReturnValueOnce(rebindResponse.promise)
    const store = useWorkflowStore()
    store.workflows = [workflowInfo('race', 'Race')]
    store.current = store.workflows[0]!

    const rebinding = store.rebindVersions()
    await store.forgetDeletedWorkflow('race')
    rebindResponse.resolve({
      data: {
        info: workflowInfo('race', 'Stale rebind'),
        graph: { nodes: [{ id: 'stale' }], edges: [] },
        missing_packages: [{ package_name: 'stale' }],
        missing_tools: [{ node_id: 'stale', tool_name: 'Stale' }],
      },
    })

    await expect(rebinding).rejects.toThrow(/changed identity/i)
    expect(store.workflows).toEqual([])
    expect(store.current).toBeNull()
    expect(store.missingPackages).toEqual([])
    expect(store.missingTools).toEqual([])
  })

  it.each(['to-folder', 'before'] as const)(
    'rejects a delayed %s move when a participating identity is removed remotely',
    async (mode) => {
      const moveResponse = deferred<any>()
      vi.mocked(api.patch).mockReturnValueOnce(moveResponse.promise)
      const store = useWorkflowStore()
      store.workflowFolders = [
        { id: 'Analysis', name: 'Analysis', parentId: null },
        { id: 'Archive', name: 'Archive', parentId: null },
      ]
      store.workflows = [
        workflowInfo('Analysis/alpha', 'Alpha'),
        workflowInfo('Archive/gamma', 'Gamma'),
      ]
      store.workflowFolderIds = {
        'Analysis/alpha': 'Analysis',
        'Archive/gamma': 'Archive',
      }
      store.workflowOrder = ['Analysis/alpha', 'Archive/gamma']

      const moving = mode === 'to-folder'
        ? store.moveWorkflowToFolder('Analysis/alpha', 'Archive')
        : store.moveWorkflowBefore('Analysis/alpha', 'Archive/gamma')
      const removedIdentity = mode === 'to-folder'
        ? 'Analysis/alpha'
        : 'Archive/alpha'
      await store.forgetDeletedWorkflow(removedIdentity)
      moveResponse.resolve({ data: workflowInfo('Archive/alpha', 'Stale move') })

      await expect(moving).rejects.toThrow(/changed identity/i)
      expect(store.workflows.some(item => item.id === 'Archive/alpha')).toBe(false)
      expect(autoSaveMocks.renameWorkflow).not.toHaveBeenCalled()
    },
  )

  it.each(['rename', 'move'] as const)(
    'rejects a delayed folder %s when a descendant destination is removed remotely',
    async (mode) => {
      const folderResponse = deferred<any>()
      vi.mocked(api.patch).mockReturnValueOnce(folderResponse.promise)
      const store = useWorkflowStore()
      store.workflowFolders = [
        { id: 'Analysis', name: 'Analysis', parentId: null },
        { id: 'Archive', name: 'Archive', parentId: null },
      ]
      store.workflows = [workflowInfo('Analysis/alpha', 'Alpha')]
      store.workflowFolderIds = { 'Analysis/alpha': 'Analysis' }
      store.workflowOrder = ['Analysis/alpha']

      const moving = mode === 'rename'
        ? store.renameWorkflowFolder('Analysis', 'Renamed')
        : store.moveWorkflowFolder('Analysis', 'Archive')
      const nextFolder = mode === 'rename' ? 'Renamed' : 'Archive/Analysis'
      await store.forgetDeletedWorkflow(`${nextFolder}/alpha`)
      folderResponse.resolve({
        data: {
          path: nextFolder,
          display_name: nextFolder,
          folders: [],
          workflows: [],
        },
      })

      await expect(moving).rejects.toThrow(/changed identity/i)
      expect(store.workflows.map(item => item.id)).toEqual(['Analysis/alpha'])
      expect(autoSaveMocks.renameWorkflow).not.toHaveBeenCalled()
      expect(api.get).not.toHaveBeenCalled()
    },
  )

  it('rejects delayed child promotion after a destination is removed remotely', async () => {
    const deleteResponse = deferred<any>()
    vi.mocked(api.delete).mockReturnValueOnce(deleteResponse.promise)
    const store = useWorkflowStore()
    store.workflowFolders = [{ id: 'Analysis', name: 'Analysis', parentId: null }]
    store.workflows = [workflowInfo('Analysis/alpha', 'Alpha')]
    store.workflowFolderIds = { 'Analysis/alpha': 'Analysis' }
    store.workflowOrder = ['Analysis/alpha']

    const promoting = store.deleteWorkflowFolder('Analysis', 'move_children_up')
    await store.forgetDeletedWorkflow('alpha')
    deleteResponse.resolve({ data: { deleted: true } })

    await expect(promoting).rejects.toThrow(/changed identity/i)
    expect(store.workflows.some(item => item.id === 'alpha')).toBe(false)
    expect(autoSaveMocks.renameWorkflow).not.toHaveBeenCalled()
    expect(api.get).not.toHaveBeenCalled()
  })

  it('finishes a delayed rename against its original canvas presentation', async () => {
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'a' })
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'b' })
    const workflowA = { name: 'a', display_name: 'Workflow A' } as WorkflowInfo
    const workflowB = { name: 'b', display_name: 'Workflow B' } as WorkflowInfo
    const store = useWorkflowStore()
    const ui = useUIStore()
    store.workflows = [workflowA, workflowB]
    store.current = workflowA
    ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
    ui.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
    canvasSessionRegistry.activate(canvasA)
    let resolveRename!: (value: { data: WorkflowInfo }) => void
    vi.mocked(api.patch).mockReturnValueOnce(new Promise((resolve) => {
      resolveRename = resolve
    }))

    const rename = store.patchWorkflow('a', {
      action: 'update',
      display_name: 'Workflow A renamed',
    }, {
      canvasId: canvasA,
      workflowName: 'a',
    })
    canvasSessionRegistry.activate(canvasB)
    store.current = workflowB
    resolveRename({
      data: { ...workflowA, display_name: 'Workflow A renamed' },
    })
    await rename

    expect(store.currentName).toBe('b')
    expect(ui.activeWorkflowName).toBe('Workflow B')
    canvasSessionRegistry.activate(canvasA)
    expect(ui.activeWorkflowName).toBe('Workflow A renamed')
  })

  it('does not rename or clean an active canvas while loading another workflow', async () => {
    const canvasA = canvasIdFromPanelId('workflow:a')
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'a' })
    canvasSessionRegistry.activate(canvasA)
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
    ui.markCanvasDirty(canvasA)
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        info: {
          name: 'b',
          display_name: 'Workflow B',
          path: '/tmp/b.json',
          last_modified: '2026-07-15T10:00:00Z',
        },
        graph: { nodes: [], edges: [] },
        missing_packages: [],
        missing_tools: [],
      },
    })

    const store = useWorkflowStore()
    await store.loadWorkflow('b')

    expect(store.currentName).toBe('b')
    expect(ui.activeWorkflowId).toBe('a')
    expect(ui.activeWorkflowName).toBe('Workflow A')
    expect(ui.hasUnsavedChanges).toBe(true)
  })

  it('keeps identity and autosave keys stable after a display-name update', async () => {
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        name: 'Untitled',
        display_name: 'New workflow',
        path: '/tmp/Untitled.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    })
    const store = useWorkflowStore()
    store.workflows = [{
      name: 'Untitled',
      display_name: 'Untitled',
      path: '/tmp/Untitled.json',
      last_modified: '2026-04-30T11:00:00Z',
    }]
    store.current = store.workflows[0]
    const drafts = useWorkflowDraftStore()
    drafts.reset('Untitled')
    noteRemoteDraft('Untitled', 4)

    const renamed = await store.patchWorkflow('Untitled', {
      action: 'update',
      display_name: 'New workflow',
    })

    expect(renamed.name).toBe('Untitled')
    expect(store.currentName).toBe('Untitled')
    expect(store.workflows.map((workflow) => workflow.name)).toEqual(['Untitled'])
    expect(autoSaveMocks.renameWorkflow).not.toHaveBeenCalled()
    expect(autoSaveMocks.setLastOpenedWorkflow).not.toHaveBeenCalled()
    drafts.trackWorkflow('Untitled')
    expect(drafts.remoteAvailableRevision).toBe(4)
  })

  it('keeps the source workflow listed when duplicating', async () => {
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        name: 'copy',
        display_name: 'Copy',
        path: '/tmp/copy.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    })
    const store = useWorkflowStore()
    store.workflows = [{
      name: 'source',
      display_name: 'Source',
      path: '/tmp/source.json',
      last_modified: '2026-04-30T11:00:00Z',
    }]
    store.current = store.workflows[0]

    await store.patchWorkflow('source', {
      action: 'duplicate',
      new_name: 'copy',
      display_name: 'Copy',
    })

    expect(store.workflows.map((workflow) => workflow.name).sort()).toEqual(['copy', 'source'])
    expect(autoSaveMocks.renameWorkflow).not.toHaveBeenCalled()
    expect(autoSaveMocks.setLastOpenedWorkflow).not.toHaveBeenCalled()
  })

  it('downloads exported workflows using the server filename', async () => {
    const blob = new Blob(['zip'], { type: 'application/zip' })
    const createObjectURL = vi
      .spyOn(window.URL, 'createObjectURL')
      .mockReturnValue('blob:workflow')
    const revokeObjectURL = vi
      .spyOn(window.URL, 'revokeObjectURL')
      .mockImplementation(() => {})
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})
    vi.mocked(api.post).mockResolvedValueOnce({
      data: blob,
      headers: { 'content-disposition': 'attachment; filename="wf.bioimageflow.zip"' },
    })
    const store = useWorkflowStore()

    await store.exportWorkflow('wf')

    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/workflows/wf/export',
      undefined,
      { responseType: 'blob' },
    )
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    const anchor = document.querySelector('a[download="wf.bioimageflow.zip"]')
    expect(anchor).toBeNull()
    expect(click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:workflow')
  })

  it('falls back to a BioImageFlow zip archive filename when export has no server filename', async () => {
    const blob = new Blob(['zip'], { type: 'application/zip' })
    vi.spyOn(window.URL, 'createObjectURL').mockReturnValue('blob:workflow')
    vi.spyOn(window.URL, 'revokeObjectURL').mockImplementation(() => {})
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})
    vi.mocked(api.post).mockResolvedValueOnce({
      data: blob,
      headers: {},
    })
    const store = useWorkflowStore()

    await store.exportWorkflow('wf')

    expect(document.querySelector('a[download="wf.bioimageflow.zip"]')).toBeNull()
    expect(click).toHaveBeenCalled()
  })

  it('uploads import files as FormData and stores missing dependency data', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        info: {
          name: 'imported',
          display_name: 'Imported',
          path: '/tmp/imported.json',
          last_modified: '2026-04-30T12:00:00Z',
        },
        missing_packages: [{
          package_name: 'pkg',
          required_version: '1.0.0',
          installed_versions: [],
          affected_nodes: ['n1'],
        }],
        missing_tools: [{
          node_id: 'n1',
          tool_name: 'Tool',
          installed_versions: [],
        }],
      },
    })
    const store = useWorkflowStore()
    const file = new File(['zip'], 'workflow.bioimageflow.zip', {
      type: 'application/zip',
    })

    const response = await store.importWorkflow(file, { nameOverride: 'imported' })

    expect(response.info.name).toBe('imported')
    const [url, body, config] = vi.mocked(api.post).mock.calls[0]
    expect(url).toBe('/api/v1/workflows/import')
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get('file')).toBe(file)
    expect((body as FormData).get('name_override')).toBe('imported')
    expect(config).toBeUndefined()
    expect(store.workflows.map((workflow) => workflow.name)).toEqual(['imported'])
    expect(store.missingPackages[0].package_name).toBe('pkg')
    expect(store.missingTools[0].tool_name).toBe('Tool')
  })

  it('fetches the backend workflow tree and keeps a compatible flat list', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        path: '',
        display_name: 'Workflows',
        folders: [{
          path: 'Analysis',
          display_name: 'Analysis',
          folders: [],
          workflows: [{
            name: 'analysis/beta',
            folder: 'Analysis',
            display_name: 'Beta',
            path: '/tmp/Analysis/beta.json',
            last_modified: '2026-04-30T12:00:00Z',
          }],
        }],
        workflows: [{
          name: 'alpha',
          folder: '',
          display_name: 'Alpha',
          path: '/tmp/alpha.json',
          last_modified: '2026-04-30T11:00:00Z',
        }],
      },
    })
    const store = useWorkflowStore()

    await store.fetchWorkflowTree()

    expect(api.get).toHaveBeenCalledWith('/api/v1/workflows/tree')
    expect(store.workflowFolders).toEqual([{
      id: 'Analysis',
      name: 'Analysis',
      parentId: null,
    }])
    expect(store.workflowFolderIds['analysis/beta']).toBe('Analysis')
    expect(store.workflows.map((workflow) => workflow.name).sort()).toEqual([
      'alpha',
      'analysis/beta',
    ])
    expect(store.flattenedWorkflows.map((workflow) => workflow.name)).toEqual([
      'alpha',
      'analysis/beta',
    ])
  })

  it('retries a stale flat-list response that crosses workflow deletion', async () => {
    const staleResponse = deferred<any>()
    vi.mocked(api.get)
      .mockReturnValueOnce(staleResponse.promise)
      .mockResolvedValueOnce({ data: [workflowInfo('kept', 'Kept')] })
    const store = useWorkflowStore()

    const refresh = store.fetchWorkflows()
    await store.forgetDeletedWorkflow('deleted')
    staleResponse.resolve({
      data: [
        workflowInfo('deleted', 'Deleted generation'),
        workflowInfo('kept', 'Kept'),
      ],
    })
    await refresh

    expect(api.get).toHaveBeenCalledTimes(2)
    expect(store.workflows.map(workflow => workflow.id)).toEqual(['kept'])
  })

  it('retries a stale tree response that crosses workflow deletion', async () => {
    const staleResponse = deferred<any>()
    const tree = (workflows: WorkflowInfo[]) => ({
      path: '',
      display_name: 'Workflows',
      folders: [],
      workflows,
    })
    vi.mocked(api.get)
      .mockReturnValueOnce(staleResponse.promise)
      .mockResolvedValueOnce({ data: tree([workflowInfo('kept', 'Kept')]) })
    const store = useWorkflowStore()

    const refresh = store.fetchWorkflowTree()
    await store.forgetDeletedWorkflow('deleted')
    staleResponse.resolve({
      data: tree([
        workflowInfo('deleted', 'Deleted generation'),
        workflowInfo('kept', 'Kept'),
      ]),
    })
    await refresh

    expect(api.get).toHaveBeenCalledTimes(2)
    expect(store.workflows.map(workflow => workflow.id)).toEqual(['kept'])
  })

  it('turns import conflicts into WorkflowConflictError', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new AxiosError(
      'conflict',
      undefined,
      undefined,
      undefined,
      {
        status: 409,
        statusText: 'Conflict',
        headers: {},
        config: {} as any,
        data: {
          detail: "Workflow 'wf' already exists",
          suggested_name: 'wf_2',
        },
      },
    ))
    const store = useWorkflowStore()
    const file = new File(['zip'], 'workflow.bioimageflow.zip', {
      type: 'application/zip',
    })

    await expect(store.importWorkflow(file)).rejects.toMatchObject({
      name: 'WorkflowConflictError',
      suggestedName: 'wf_2',
    })
  })

  it.each([
    ['new_id', { new_id: 'Archive/renamed' }],
    ['new_name', { new_name: 'renamed' }],
    ['folder', { folder: 'Archive' }],
  ])('rejects an open workflow update that changes identity through %s', async (_, identityPatch) => {
    const store = useWorkflowStore()
    const ui = useUIStore()
    const workflow = workflowInfo('Analysis/alpha', 'Alpha')
    store.workflows = [workflow]
    store.workflowFolders = [
      { id: 'Analysis', name: 'Analysis', parentId: null },
      { id: 'Archive', name: 'Archive', parentId: null },
    ]
    store.workflowFolderIds = { 'Analysis/alpha': 'Analysis' }
    store.workflowOrder = ['Analysis/alpha']
    const canvasId = registerWorkflowCanvas('Analysis/alpha')
    const descriptor = canvasSessionRegistry.get(canvasId)?.descriptor

    await expect(store.patchWorkflow('Analysis/alpha', {
      action: 'update',
      ...identityPatch,
    })).rejects.toThrow(/close.*workflow.*sub-workflow.*tab/is)

    expect(api.patch).not.toHaveBeenCalled()
    expect(autoSaveMocks.renameWorkflow).not.toHaveBeenCalled()
    expect(store.workflows).toEqual([workflow])
    expect(store.workflowFolderIds).toEqual({ 'Analysis/alpha': 'Analysis' })
    expect(ui.canvasWorkflowId(canvasId)).toBe('Analysis/alpha')
    expect(canvasSessionRegistry.get(canvasId)?.descriptor).toBe(descriptor)
  })

  it('allows display and metadata updates without changing an open workflow identity', async () => {
    const store = useWorkflowStore()
    const ui = useUIStore()
    const workflow = workflowInfo('Analysis/alpha', 'Alpha')
    store.workflows = [workflow]
    const canvasId = registerWorkflowCanvas('Analysis/alpha')
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        ...workflow,
        display_name: 'Renamed display',
        description: 'Updated description',
      },
    })

    const updated = await store.patchWorkflow('Analysis/alpha', {
      action: 'update',
      display_name: 'Renamed display',
      description: 'Updated description',
    }, {
      canvasId,
      workflowName: 'Analysis/alpha',
    })

    expect(api.patch).toHaveBeenCalledWith(
      '/api/v1/workflows/Analysis/alpha',
      {
        action: 'update',
        display_name: 'Renamed display',
        description: 'Updated description',
      },
    )
    expect(updated.id).toBe('Analysis/alpha')
    expect(ui.canvasWorkflowId(canvasId)).toBe('Analysis/alpha')
    expect(canvasSessionRegistry.get(canvasId)?.descriptor).toMatchObject({
      kind: 'root',
      workflowId: 'Analysis/alpha',
    })
  })

  it('rejects workflow moves across folders while allowing same-folder reorder', async () => {
    const store = useWorkflowStore()
    store.workflowFolders = [
      { id: 'Analysis', name: 'Analysis', parentId: null },
      { id: 'Archive', name: 'Archive', parentId: null },
    ]
    store.workflows = [
      workflowInfo('Analysis/alpha', 'Alpha'),
      workflowInfo('Analysis/beta', 'Beta'),
      workflowInfo('Archive/gamma', 'Gamma'),
    ]
    store.workflowFolderIds = {
      'Analysis/alpha': 'Analysis',
      'Analysis/beta': 'Analysis',
      'Archive/gamma': 'Archive',
    }
    store.workflowOrder = ['Analysis/beta', 'Analysis/alpha', 'Archive/gamma']
    registerWorkflowCanvas('Analysis/alpha')

    await expect(
      store.moveWorkflowToFolder('Analysis/alpha', 'Archive'),
    ).rejects.toThrow(/close.*tab/is)
    await expect(
      store.moveWorkflowBefore('Analysis/alpha', 'Archive/gamma'),
    ).rejects.toThrow(/close.*tab/is)

    expect(api.patch).not.toHaveBeenCalled()
    expect(store.workflowOrder).toEqual([
      'Analysis/beta',
      'Analysis/alpha',
      'Archive/gamma',
    ])

    await store.moveWorkflowBefore('Analysis/alpha', 'Analysis/beta')

    expect(api.patch).not.toHaveBeenCalled()
    expect(store.workflowOrder).toEqual([
      'Analysis/alpha',
      'Analysis/beta',
      'Archive/gamma',
    ])
  })

  it('rejects folder rename when a registered root canvas presents a descendant workflow', async () => {
    const store = useWorkflowStore()
    store.workflowFolders = [
      { id: 'Analysis', name: 'Analysis', parentId: null },
      { id: 'Analysis/Nested', name: 'Nested', parentId: 'Analysis' },
    ]
    store.workflows = [workflowInfo('Analysis/Nested/alpha', 'Alpha')]
    registerWorkflowCanvas('Analysis/Nested/alpha')

    await expect(
      store.renameWorkflowFolder('Analysis', 'Renamed'),
    ).rejects.toThrow(/close.*workflow.*sub-workflow.*tab/is)

    expect(api.patch).not.toHaveBeenCalled()
    expect(store.workflowFolders[0]).toEqual({
      id: 'Analysis',
      name: 'Analysis',
      parentId: null,
    })
  })

  it('rejects folder move when a registered nested canvas presents a descendant workflow', async () => {
    const store = useWorkflowStore()
    const ui = useUIStore()
    store.workflowFolders = [
      { id: 'Analysis', name: 'Analysis', parentId: null },
      { id: 'Analysis/Nested', name: 'Nested', parentId: 'Analysis' },
      { id: 'Archive', name: 'Archive', parentId: null },
    ]
    store.workflows = [workflowInfo('Analysis/Nested/alpha', 'Alpha')]
    const canvasId = registerWorkflowCanvas('Analysis/Nested/alpha', 'nested')
    const descriptor = canvasSessionRegistry.get(canvasId)?.descriptor

    await expect(
      store.moveWorkflowFolder('Analysis/Nested', 'Archive'),
    ).rejects.toThrow(/close.*workflow.*sub-workflow.*tab/is)

    expect(api.patch).not.toHaveBeenCalled()
    expect(ui.canvasWorkflowId(canvasId)).toBe('Analysis/Nested/alpha')
    expect(canvasSessionRegistry.get(canvasId)?.descriptor).toBe(descriptor)
  })

  it('rejects child promotion when a promoted workflow is open', async () => {
    const store = useWorkflowStore()
    store.workflowFolders = [
      { id: 'Analysis', name: 'Analysis', parentId: null },
    ]
    store.workflows = [workflowInfo('Analysis/alpha', 'Alpha')]
    registerWorkflowCanvas('Analysis/alpha')

    await expect(
      store.deleteWorkflowFolder('Analysis', 'move_children_up'),
    ).rejects.toThrow(/close.*tab/is)

    expect(api.delete).not.toHaveBeenCalled()
    expect(autoSaveMocks.renameWorkflow).not.toHaveBeenCalled()
    expect(store.workflowFolders).toEqual([
      { id: 'Analysis', name: 'Analysis', parentId: null },
    ])
  })

  it('rejects direct deletion while a nested canvas presents the workflow', async () => {
    const store = useWorkflowStore()
    const workflow = workflowInfo('Analysis/alpha', 'Alpha')
    store.workflows = [workflow]
    const canvasId = registerWorkflowCanvas('Analysis/alpha', 'nested')
    const descriptor = canvasSessionRegistry.get(canvasId)?.descriptor

    await expect(store.deleteWorkflow('Analysis/alpha')).rejects.toThrow(/close.*tab/is)

    expect(api.delete).not.toHaveBeenCalled()
    expect(autoSaveMocks.clearAutoSave).not.toHaveBeenCalled()
    expect(autoSaveMocks.clearAutoSaveStrict).not.toHaveBeenCalled()
    expect(store.workflows).toEqual([workflow])
    expect(canvasSessionRegistry.get(canvasId)?.descriptor).toBe(descriptor)
  })

  it('allows direct deletion after the presenting canvas is unregistered', async () => {
    const store = useWorkflowStore()
    store.workflows = [workflowInfo('Analysis/alpha', 'Alpha')]
    const canvasId = registerWorkflowCanvas('Analysis/alpha')
    canvasSessionRegistry.unregister(canvasId)
    vi.mocked(api.delete).mockResolvedValueOnce({ data: { deleted: true } })

    await store.deleteWorkflow('Analysis/alpha')

    expect(api.delete).toHaveBeenCalledWith('/api/v1/workflows/Analysis/alpha')
    expect(store.workflows).toEqual([])
  })

  it('does not let a confirmed closing canvas exempt another open owner', async () => {
    const store = useWorkflowStore()
    store.workflows = [workflowInfo('Analysis/alpha', 'Alpha')]
    const closingCanvasId = registerWorkflowCanvas('Analysis/alpha')
    registerWorkflowCanvas('Analysis/alpha', 'nested')

    await expect(store.deleteWorkflow('Analysis/alpha', {
      closingCanvasId,
    })).rejects.toThrow(/close.*tab/is)

    expect(api.delete).not.toHaveBeenCalled()
    expect(store.workflows).toHaveLength(1)
  })

  it('rejects deleting a folder subtree while any descendant workflow is open', async () => {
    const store = useWorkflowStore()
    store.workflowFolders = [
      { id: 'Analysis', name: 'Analysis', parentId: null },
      { id: 'Analysis/Nested', name: 'Nested', parentId: 'Analysis' },
    ]
    store.workflows = [workflowInfo('Analysis/Nested/alpha', 'Alpha')]
    registerWorkflowCanvas('Analysis/Nested/alpha')

    await expect(
      store.deleteWorkflowFolder('Analysis', 'delete_children'),
    ).rejects.toThrow(/close.*tab/is)

    expect(api.delete).not.toHaveBeenCalled()
    expect(autoSaveMocks.clearAutoSave).not.toHaveBeenCalled()
    expect(autoSaveMocks.clearAutoSaveStrict).not.toHaveBeenCalled()
    expect(store.workflowFolders).toHaveLength(2)
    expect(store.workflows).toHaveLength(1)
  })

  it('rejects a child open that resolves after its folder subtree was deleted', async () => {
    const staleWorkflow = deferred<any>()
    vi.mocked(api.get)
      .mockReturnValueOnce(staleWorkflow.promise)
      .mockResolvedValueOnce({
        data: {
          path: '',
          display_name: 'Workflows',
          folders: [],
          workflows: [],
        },
      })
    vi.mocked(api.delete).mockResolvedValueOnce({ data: { deleted: true } })
    const store = useWorkflowStore()
    store.workflowFolders = [{ id: 'Analysis', name: 'Analysis', parentId: null }]
    store.workflows = [workflowInfo('Analysis/race', 'Deleted generation')]

    const opening = store.loadWorkflow('Analysis/race')
    await store.deleteWorkflowFolder('Analysis', 'delete_children')
    staleWorkflow.resolve({
      data: {
        info: workflowInfo('Analysis/race', 'Stale generation'),
        graph: { nodes: [], edges: [] },
        missing_packages: [],
        missing_tools: [],
      },
    })

    await expect(opening).rejects.toThrow(/changed identity/i)
    expect(store.workflows).toEqual([])
  })

  it('ignores stale workflow presentations after their canvas session closes', async () => {
    const store = useWorkflowStore()
    const canvasId = canvasIdFromPanelId('closed:Analysis/alpha')
    store.workflowFolders = [
      { id: 'Analysis', name: 'Analysis', parentId: null },
      { id: 'Archive', name: 'Archive', parentId: null },
    ]
    store.workflows = [workflowInfo('Analysis/alpha', 'Alpha')]
    store.workflowFolderIds = { 'Analysis/alpha': 'Analysis' }
    store.workflowOrder = ['Analysis/alpha']
    useUIStore().setCanvasWorkflow(canvasId, 'Analysis/alpha', 'Alpha')
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: workflowInfo('Archive/alpha', 'Alpha'),
    })

    await store.moveWorkflowToFolder('Analysis/alpha', 'Archive')

    expect(api.patch).toHaveBeenCalledOnce()
    expect(store.workflows.map(workflow => workflow.id)).toEqual(['Archive/alpha'])
    expect(useUIStore().canvasWorkflowId(canvasId)).toBe('Analysis/alpha')
  })

  it('organizes workflows into folders while exposing a flattened workflow list', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        path: 'Analysis',
        display_name: 'Analysis',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        id: 'Analysis/beta',
        name: 'beta',
        folder: 'Analysis',
        display_name: 'Beta',
        path: '/tmp/Analysis/beta.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    })
    const store = useWorkflowStore()
    store.workflows = [
      {
        name: 'alpha',
        display_name: 'Alpha',
        path: '/tmp/alpha.json',
        last_modified: '2026-04-30T11:00:00Z',
      },
      {
        name: 'beta',
        display_name: 'Beta',
        path: '/tmp/beta.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    ]
    const folder = await store.createWorkflowFolder('Analysis')
    await store.moveWorkflowToFolder('beta', folder.id)

    expect(store.workflowTree[1]).toMatchObject({
      type: 'folder',
      id: folder.id,
      name: 'Analysis',
    })
    expect(store.flattenedWorkflows.map((workflow) => workflow.name)).toEqual([
      'alpha',
      'beta',
    ])
  })

  it('keeps returned workflow ids when moving a workflow into a folder with spaces', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        path: 'Analysis Results',
        display_name: 'Analysis Results',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        id: 'Analysis Results/beta',
        name: 'beta',
        folder: 'Analysis Results',
        display_name: 'Beta',
        path: '/tmp/Analysis Results/beta/workflow.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    })
    const store = useWorkflowStore()
    store.workflows = [
      {
        id: 'beta',
        name: 'beta',
        display_name: 'Beta',
        path: '/tmp/beta/workflow.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    ]
    const drafts = useWorkflowDraftStore()
    drafts.reset('beta')
    noteRemoteDraft('beta', 5)
    noteRemoteDraft('Analysis Results/beta', 6)

    const folder = await store.createWorkflowFolder('Analysis Results')
    await store.moveWorkflowToFolder('beta', folder.id)

    expect(api.post).toHaveBeenCalledWith('/api/v1/workflows/folders', {
      path: 'Analysis Results',
    })
    expect(api.patch).toHaveBeenCalledWith(
      '/api/v1/workflows/beta',
      { action: 'update', folder: 'Analysis Results' },
    )
    expect(store.workflowFolderIds).toEqual({
      'Analysis Results/beta': 'Analysis Results',
    })
    expect(store.flattenedWorkflows.map((workflow) => (
      (workflow as WorkflowInfo & { id?: string }).id || workflow.name
    ))).toEqual(['Analysis Results/beta'])
    drafts.trackWorkflow('beta')
    expect(drafts.remoteAvailableRevision).toBeNull()
    drafts.trackWorkflow('Analysis Results/beta')
    expect(drafts.remoteAvailableRevision).toBe(6)
  })

  it('updates the active workflow identity when moving it into a folder', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        path: 'Analysis Results',
        display_name: 'Analysis Results',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        id: 'Analysis Results/beta',
        name: 'beta',
        folder: 'Analysis Results',
        display_name: 'Beta',
        path: '/tmp/Analysis Results/beta/workflow.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    })
    vi.mocked(api.put).mockResolvedValueOnce({
      data: {
        id: 'Analysis Results/beta',
        name: 'beta',
        folder: 'Analysis Results',
        display_name: 'Beta',
        path: '/tmp/Analysis Results/beta/workflow.json',
        last_modified: '2026-04-30T12:01:00Z',
      },
    })
    const store = useWorkflowStore()
    const workflow: WorkflowInfo = {
      id: 'beta',
      name: 'beta',
      display_name: 'Beta',
      path: '/tmp/beta/workflow.json',
      last_modified: '2026-04-30T12:00:00Z',
    }
    store.workflows = [workflow]
    store.current = workflow
    const folder = await store.createWorkflowFolder('Analysis Results')
    await store.moveWorkflowToFolder('beta', folder.id)
    await store.saveWorkflow({ nodes: [], edges: [] })

    expect(store.currentName).toBe('Analysis Results/beta')
    expect(autoSaveMocks.renameWorkflow).toHaveBeenCalledWith(
      'beta',
      'Analysis Results/beta',
    )
    expect(autoSaveMocks.setLastOpenedWorkflow).toHaveBeenCalledWith(
      'Analysis Results/beta',
    )
    expect(api.put).toHaveBeenCalledWith(
      '/api/v1/workflows/Analysis%20Results/beta',
      { graph: { nodes: [], edges: [] } },
    )
  })

  it('renames and deletes workflow folders without deleting workflows', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        path: 'Drafts',
        display_name: 'Drafts',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.patch)
      .mockResolvedValueOnce({
        data: {
          id: 'Drafts/alpha',
          name: 'alpha',
          folder: 'Drafts',
          display_name: 'Alpha',
          path: '/tmp/Drafts/alpha.json',
          last_modified: '2026-04-30T11:00:00Z',
        },
      })
      .mockResolvedValueOnce({
        data: {
          path: 'Published',
          display_name: 'Published',
          folders: [],
          workflows: [],
        },
      })
    vi.mocked(api.get)
      .mockResolvedValueOnce({
        data: {
          path: '',
          display_name: 'workspace',
          folders: [{
            path: 'Published',
            display_name: 'Published',
            folders: [],
            workflows: [{
              id: 'Published/alpha',
              name: 'alpha',
              folder: 'Published',
              display_name: 'Alpha',
              path: '/tmp/Published/alpha.json',
              last_modified: '2026-04-30T11:00:00Z',
            }],
          }],
          workflows: [],
        },
      })
      .mockResolvedValueOnce({
        data: {
          path: '',
          display_name: 'workspace',
          folders: [],
          workflows: [{
            id: 'alpha',
            name: 'alpha',
            folder: '',
            display_name: 'Alpha',
            path: '/tmp/alpha.json',
            last_modified: '2026-04-30T11:00:00Z',
          }],
        },
      })
    vi.mocked(api.delete).mockResolvedValueOnce({ data: { deleted: true } })
    const store = useWorkflowStore()
    store.workflows = [{
      name: 'alpha',
      display_name: 'Alpha',
      path: '/tmp/alpha.json',
      last_modified: '2026-04-30T11:00:00Z',
    }]
    const folder = await store.createWorkflowFolder('Drafts')
    await store.moveWorkflowToFolder('alpha', folder.id)

    await store.renameWorkflowFolder(folder.id, 'Published')
    expect(store.workflowFolders[0].name).toBe('Published')

    await store.deleteWorkflowFolder('Published', 'move_children_up')
    expect(store.workflowFolders).toEqual([])
    expect(store.workflowFolderIds.alpha).toBeNull()
    expect(store.flattenedWorkflows.map((workflow) => workflow.name)).toEqual(['alpha'])
  })

  it('moves nested folders with spaces and remaps active workflow identity', async () => {
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        path: 'Archive 2026/Quality Control',
        display_name: 'Quality Control',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        path: '',
        display_name: 'workspace',
        folders: [{
          path: 'Archive 2026',
          display_name: 'Archive 2026',
          folders: [{
            path: 'Archive 2026/Quality Control',
            display_name: 'Quality Control',
            folders: [],
            workflows: [{
              id: 'Archive 2026/Quality Control/beta',
              name: 'beta',
              folder: 'Archive 2026/Quality Control',
              display_name: 'Beta',
              path: '/tmp/Archive 2026/Quality Control/beta/workflow.json',
              last_modified: '2026-04-30T12:00:00Z',
            }],
          }],
          workflows: [],
        }],
        workflows: [],
      },
    })
    const store = useWorkflowStore()
    const workflow: WorkflowInfo = {
      id: 'Analysis Results/Quality Control/beta',
      name: 'beta',
      folder: 'Analysis Results/Quality Control',
      display_name: 'Beta',
      path: '/tmp/Analysis Results/Quality Control/beta/workflow.json',
      last_modified: '2026-04-30T12:00:00Z',
    }
    store.workflowFolders = [
      { id: 'Analysis Results', name: 'Analysis Results', parentId: null },
      {
        id: 'Analysis Results/Quality Control',
        name: 'Quality Control',
        parentId: 'Analysis Results',
      },
      { id: 'Archive 2026', name: 'Archive 2026', parentId: null },
    ]
    store.workflows = [workflow]
    store.workflowFolderIds = {
      'Analysis Results/Quality Control/beta': 'Analysis Results/Quality Control',
    }
    store.workflowOrder = ['Analysis Results/Quality Control/beta']
    store.current = workflow
    const drafts = useWorkflowDraftStore()
    drafts.reset('Analysis Results/Quality Control/beta')
    noteRemoteDraft('Analysis Results/Quality Control/beta', 7)

    await store.moveWorkflowFolder('Analysis Results/Quality Control', 'Archive 2026')

    expect(api.patch).toHaveBeenCalledWith(
      '/api/v1/workflows/folders/Analysis%20Results/Quality%20Control',
      { new_path: 'Archive 2026/Quality Control' },
    )
    expect(autoSaveMocks.renameWorkflow).toHaveBeenCalledWith(
      'Analysis Results/Quality Control/beta',
      'Archive 2026/Quality Control/beta',
    )
    expect(store.currentName).toBe('Archive 2026/Quality Control/beta')
    expect(store.workflowFolders).toContainEqual({
      id: 'Archive 2026/Quality Control',
      name: 'Quality Control',
      parentId: 'Archive 2026',
    })
    drafts.trackWorkflow('Analysis Results/Quality Control/beta')
    expect(drafts.remoteAvailableRevision).toBeNull()
  })

  it('forgets retained child drafts when deleting a folder with its children', async () => {
    vi.mocked(api.delete).mockResolvedValueOnce({ data: { deleted: true } })
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        path: '',
        display_name: 'workspace',
        folders: [],
        workflows: [],
      },
    })
    const store = useWorkflowStore()
    store.workflowFolders = [
      { id: 'Archive', name: 'Archive', parentId: null },
      { id: 'Archive/Nested', name: 'Nested', parentId: 'Archive' },
    ]
    store.workflows = [
      {
        id: 'Archive/alpha',
        name: 'alpha',
        display_name: 'Alpha',
        path: '/tmp/Archive/alpha/workflow.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
      {
        id: 'Archive/Nested/beta',
        name: 'beta',
        display_name: 'Beta',
        path: '/tmp/Archive/Nested/beta/workflow.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    ]
    const drafts = useWorkflowDraftStore()
    drafts.reset('outside')
    for (const workflowId of ['Archive/alpha', 'Archive/Nested/beta']) {
      noteRemoteDraft(workflowId, 3)
    }

    await store.deleteWorkflowFolder('Archive', 'delete_children')

    for (const workflowId of ['Archive/alpha', 'Archive/Nested/beta']) {
      drafts.trackWorkflow(workflowId)
      expect(drafts.remoteAvailableRevision).toBeNull()
    }
  })

  it('sorts workflows and folders alphabetically within each folder', async () => {
    const store = useWorkflowStore()
    store.workflowFolders = [
      { id: 'Z Folder', name: 'Z Folder', parentId: null },
    ]
    store.workflows = [
      {
        name: 'alpha',
        display_name: 'Alpha',
        path: '/tmp/alpha.json',
        last_modified: '2026-04-30T11:00:00Z',
      },
      {
        name: 'beta',
        display_name: 'Beta',
        path: '/tmp/beta.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    ]

    expect(store.workflowTree.map((node) => (
      node.type === 'folder' ? node.name : node.workflow.display_name
    ))).toEqual(['Alpha', 'Beta', 'Z Folder'])
  })

  it('keeps alphabetical workflow order even when workflow ids are moved before another id', async () => {
    const store = useWorkflowStore()
    store.workflows = [
      {
        name: 'alpha',
        display_name: 'Alpha',
        path: '/tmp/alpha.json',
        last_modified: '2026-04-30T11:00:00Z',
      },
      {
        name: 'beta',
        display_name: 'Beta',
        path: '/tmp/beta.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    ]

    await store.moveWorkflowBefore('beta', 'alpha')

    expect(store.flattenedWorkflows.map((workflow) => workflow.name)).toEqual([
      'alpha',
      'beta',
    ])
  })
})
