import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { SettingsResponse, WorkflowInfo } from '@/api/types'

vi.mock('@/api/client', () => ({ api: { get: vi.fn(), patch: vi.fn(), post: vi.fn() } }))
vi.mock('@/composables/useAutoSave', () => ({ useAutoSave: () => ({
  setLastOpenedWorkflow: vi.fn(), clearAutoSave: vi.fn(), clearAutoSaveStrict: vi.fn(),
}), writeAutoSaveEntry: vi.fn() }))

import { api } from '@/api/client'
import { useSettingsStore } from '../settings'
import { useWorkflowStore } from '../workflow'

const workflowId = 'a9acec57-a374-44d4-a2af-929e773b9efa'

function info(workspace: string, folder: string): WorkflowInfo {
  return {
    id: workflowId, name: workflowId, relative_path: `${folder}/analysis`, folder,
    display_name: `Analysis in ${workspace}`, workspace_path: workspace,
    path: `${workspace}/workflows/${folder}/analysis/workflow.json`,
    results_path: `${workspace}/workflows/${folder}/analysis/results`,
    last_modified: '2026-11-16T10:00:00Z', identity_generation: 0,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(yes => { resolve = yes })
  return { promise, resolve }
}

function tree(workflow: WorkflowInfo) {
  return { data: { path: '', display_name: 'Workflows', workflows: [], folders: [{
    path: workflow.folder, display_name: workflow.folder, workflows: [workflow], folders: [],
  }] } }
}

function selectCopiedWorkspace() {
  // A copied workspace intentionally retains the same UUID and generation.
  // Switching presentation must therefore fence more than UUID equality.
  useSettingsStore().workspaceSelectionRevision += 1
  const store = useWorkflowStore()
  const copy = info('/workspace-b', 'Selected')
  store.workflows = [copy]
  store.workflowFolders = [{ id: 'Selected', name: 'Selected', parentId: null }]
  store.workflowFolderIds = { [workflowId]: 'Selected' }
  store.selectedFolderId = 'Selected'
  store.current = copy
  return copy
}

describe('workflow responses retain workspace ownership', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(api.get).mockReset()
    vi.mocked(api.patch).mockReset()
    const store = useWorkflowStore()
    const original = info('/workspace-a', 'Original')
    store.workflows = [original]
    store.workflowFolders = [{ id: 'Original', name: 'Original', parentId: null }]
    store.workflowFolderIds = { [workflowId]: 'Original' }
    store.current = original
    store.selectedFolderId = 'Original'
  })

  it.each([null, '~/configured'])('uses the resolved canonical owner for an empty workspace folder operation (configured %s)', async configured => {
    useSettingsStore().settings = { workspace_path: configured, resolved_workspace_path: '/canonical-default' } as SettingsResponse
    const store = useWorkflowStore()
    store.workflows = []
    store.workflowFolders = []
    vi.mocked(api.post).mockResolvedValueOnce({ data: { path: 'Results', display_name: 'Results' } })
    await store.createWorkflowFolder('Results')
    expect(api.post).toHaveBeenCalledWith('/api/v1/workflows/folders', { path: 'Results' }, {
      headers: { 'X-BioImageFlow-Workspace': '/canonical-default' },
    })
  })

  it('does not publish a delayed workflow move into a copied workspace', async () => {
    const response = deferred<{ data: WorkflowInfo }>()
    vi.mocked(api.patch).mockReturnValueOnce(response.promise)
    const store = useWorkflowStore()
    const outcome = store.patchWorkflow(workflowId, { action: 'update', new_id: 'Renamed/analysis' })
    const rejected = expect(outcome).rejects.toThrow(/workspace changed/i)
    await vi.waitFor(() => expect(api.patch).toHaveBeenCalledOnce())
    expect(api.patch).toHaveBeenCalledWith(`/api/v1/workflows/${workflowId}`,
      { action: 'update', new_id: 'Renamed/analysis' },
      { headers: { 'X-BioImageFlow-Workspace': '/workspace-a' } })
    const copy = selectCopiedWorkspace()
    response.resolve({ data: info('/workspace-a', 'Renamed') })
    await rejected
    expect(store.workflows).toEqual([copy])
    expect(store.current).toEqual(copy)
    expect(store.selectedFolderId).toBe('Selected')
  })

  it('does not remap the selected folder or refresh after a delayed folder move', async () => {
    const response = deferred<{ data: { path: string } }>()
    vi.mocked(api.patch).mockReturnValueOnce(response.promise)
    const store = useWorkflowStore()
    const rejected = expect(store.renameWorkflowFolder('Original', 'Renamed')).rejects.toThrow(/workspace changed/i)
    await vi.waitFor(() => expect(api.patch).toHaveBeenCalledOnce())
    const copy = selectCopiedWorkspace()
    response.resolve({ data: { path: 'Renamed' } })
    await rejected
    expect(api.get).not.toHaveBeenCalled()
    expect(store.workflows).toEqual([copy])
    expect(store.current).toEqual(copy)
    expect(store.selectedFolderId).toBe('Selected')
  })

  it.each(['tree', 'flat'] as const)('does not publish or retry an old workspace %s read', async (endpoint) => {
    const old = deferred<{ data: unknown }>()
    const fresh = deferred<{ data: unknown }>()
    vi.mocked(api.get).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise)
    const store = useWorkflowStore()
    const read = () => endpoint === 'tree' ? store.fetchWorkflowTree() : store.fetchWorkflows()
    const rejected = expect(read()).rejects.toThrow(/workspace changed/i)
    const copy = selectCopiedWorkspace()
    const newRead = read()
    expect(api.get).toHaveBeenCalledTimes(2)
    fresh.resolve(endpoint === 'tree' ? tree(copy) : { data: [copy] })
    await newRead
    old.resolve(endpoint === 'tree' ? tree(info('/workspace-a', 'Original')) : { data: [info('/workspace-a', 'Original')] })
    await rejected
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(store.workflows).toEqual([copy])
    expect(store.current).toEqual(copy)
    expect(store.error).toBeNull()
    expect(store.isLoading).toBe(false)
  })
})
