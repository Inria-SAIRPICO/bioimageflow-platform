import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { makeGraph } from '@/test-utils/graphFixtures'
import { useWorkflowRecoveryStore } from '../workflowRecovery'
import { useWorkflowStore } from '../workflow'
import { useSettingsStore } from '../settings'
import { useUIStore } from '../ui'
import { canvasIdFromPanelId, canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import type { AutoSaveEntry } from '@/composables/useAutoSave'
import type { WorkflowFormatStatus, WorkflowInfo } from '@/api/types'

const mocks = vi.hoisted(() => ({
  entries: [] as AutoSaveEntry[], clear: vi.fn(), last: vi.fn(), fetch: vi.fn(), put: vi.fn(), ack: vi.fn(),
  resource: null as any,
}))
vi.mock('@/composables/useAutoSave', () => ({
  writeAutoSaveEntry: vi.fn(),
  useAutoSave: () => ({ loadAutoSaves: async () => mocks.entries, clearAutoSaveEntryStrict: mocks.clear, setLastOpenedWorkflow: mocks.last }),
}))
vi.mock('@/api/workflowDrafts', () => ({
  fetchWorkflowDraft: mocks.fetch, putWorkflowDraft: mocks.put,
}))
vi.mock('@/api/workflowFormats', () => ({ acknowledgeWorkflowIdentityMigrations: mocks.ack }))
vi.mock('@/composables/useCanvasPersistence', () => ({ getRootCanvasPersistenceResource: () => mocks.resource }))
vi.mock('@/services/workflowMove', () => ({ withWorkflowMove: async (_ids: string[], action: () => Promise<void>) => action() }))

const id = '804dfb8e-20c0-452d-a317-e2115ca94ce8'
const entry = (): AutoSaveEntry => ({ name: 'Analysis/nuclei', graph: makeGraph({ name: 'Analysis/nuclei', nodes: [] }), timestamp: Date.parse('2026-11-16T12:00:00Z') })
const receipt = (): WorkflowFormatStatus => ({
  notices: [], workspace_path: '/workspace', identity_migration_id: `sha256:${'a'.repeat(64)}`,
  identity_migrations: [{ old_path: 'Analysis/nuclei', identity_generation: 3, workflow_id: id }],
})
const draft = (): WorkflowDraftResponse => ({
  draft_version: 1, workflow_id: id, graph: makeGraph({ name: 'nuclei' }), draft_revision: 7,
  dirty_against_saved: false, base_saved_revision: 'sha256:saved', updated_by: 'frontend', updated_at: '2026-11-16T11:00:00Z',
  validation: { valid: true, node_statuses: {}, errors: [] },
})

describe('workflow browser identity recovery', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    canvasSessionRegistry.dispose()
    vi.clearAllMocks()
    mocks.entries = []
    mocks.resource = null
    mocks.clear.mockResolvedValue(undefined)
    mocks.last.mockResolvedValue(undefined)
    mocks.fetch.mockResolvedValue(draft())
    mocks.put.mockImplementation(async (_id, body) => ({ ...draft(), graph: body.graph, draft_revision: 8, dirty_against_saved: true }))
    mocks.ack.mockResolvedValue({ notices: [], identity_migrations: [], workspace_path: '/workspace' })
    useSettingsStore().settings = { workspace_path: '/workspace' } as any
    const info: WorkflowInfo = { id, name: id, relative_path: 'Analysis/nuclei', folder: 'Analysis', display_name: 'Nuclei', path: '/workspace/workflows/Analysis/nuclei/workflow.json', results_path: '/workspace/workflows/Analysis/nuclei/results', last_modified: '2026-11-16T11:00:00Z', identity_generation: 0 }
    useWorkflowStore().workflows = [info]
    useWorkflowStore().observeWorkflowServerIdentityGeneration(id, 0)
  })

  it('retains legacy recovery without workspace and generation for explicit resolution', async () => {
    mocks.entries = [entry()]
    const store = useWorkflowRecoveryStore()
    await store.reconcile(receipt())
    expect(store.conflicts).toEqual(mocks.entries)
    expect(mocks.put).not.toHaveBeenCalled()
    expect(mocks.clear).not.toHaveBeenCalled()
    expect(mocks.ack).not.toHaveBeenCalled()
  })

  it('automatically restores only an exact workspace and generation receipt', async () => {
    mocks.entries = [{ ...entry(), workspace_path: '/workspace', identity_generation: 3 }]
    const store = useWorkflowRecoveryStore()
    await store.reconcile(receipt())
    expect(mocks.put).toHaveBeenCalledWith(id, { graph: makeGraph({ name: 'nuclei' }), expected_revision: 7, updated_by: 'frontend' }, '/workspace')
    expect(mocks.ack).toHaveBeenCalledWith({ migration_id: receipt().identity_migration_id, entries: receipt().identity_migrations }, '/workspace')
    expect(mocks.clear).toHaveBeenCalledWith(mocks.entries[0])
    expect(store.conflicts).toEqual([])
  })

  it.each([
    { workspace_path: '/other', identity_generation: 3 },
    { workspace_path: '/workspace', identity_generation: 2 },
  ])('never guesses an owner from a reused path: %j', async metadata => {
    mocks.entries = [{ ...entry(), ...metadata }]
    const store = useWorkflowRecoveryStore()
    await store.reconcile(receipt())
    expect(store.conflicts).toHaveLength(1)
    expect(mocks.put).not.toHaveBeenCalled()
  })

  it('retains the original snapshot and receipt after a revision conflict', async () => {
    const source = entry()
    const store = useWorkflowRecoveryStore()
    store.conflicts = [source]
    mocks.put.mockRejectedValueOnce(new Error('Draft revision conflict'))
    await expect(store.restore(source, id)).rejects.toThrow('Draft revision conflict')
    expect(store.conflicts).toEqual([source])
    expect(mocks.clear).not.toHaveBeenCalled()
    expect(mocks.ack).not.toHaveBeenCalled()
  })

  it('requires explicit confirmation before replacing newer accepted edits', async () => {
    mocks.entries = [{ ...entry(), workspace_path: '/workspace', identity_generation: 3 }]
    mocks.fetch.mockResolvedValueOnce({ ...draft(), dirty_against_saved: true, updated_at: '2026-11-16T13:00:00Z' })
    const store = useWorkflowRecoveryStore()
    await store.reconcile(receipt())
    expect(store.conflicts).toHaveLength(1)
    expect(mocks.put).not.toHaveBeenCalled()
    await store.restore(store.conflicts[0]!, id)
    expect(mocks.put).toHaveBeenCalledOnce()
    expect(mocks.clear).toHaveBeenCalledOnce()
  })

  it('installs the accepted graph and revision into a mounted destination before releasing recovery', async () => {
    const canvasId = canvasIdFromPanelId(`workflow:${id}`)
    canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: id })
    useUIStore().setCanvasWorkflow(canvasId, id, 'Nuclei')
    mocks.resource = { resolveFromDraft: vi.fn() }
    const install = vi.fn((event: Event) => {
      const detail = (event as CustomEvent).detail
      expect(mocks.resource.resolveFromDraft).toHaveBeenCalledWith(expect.objectContaining({ draft_revision: 8 }), 'external')
      expect(detail.dirty).toBe(true)
      expect(detail.draft.graph.name).toBe('nuclei')
      expect(mocks.clear).not.toHaveBeenCalled()
      detail.handled = true
      detail.resolve()
    })
    window.addEventListener('bioimageflow:restore-saved-canvas', install)
    try {
      await useWorkflowRecoveryStore().restore(entry(), id)
      expect(install).toHaveBeenCalledOnce()
      expect(mocks.clear).toHaveBeenCalledOnce()
    } finally {
      window.removeEventListener('bioimageflow:restore-saved-canvas', install)
    }
  })

  it('does not write recovery into a workspace selected while the destination is loading', async () => {
    let resolve!: (value: WorkflowDraftResponse) => void
    mocks.fetch.mockReturnValueOnce(new Promise<WorkflowDraftResponse>(accept => { resolve = accept }))
    const store = useWorkflowRecoveryStore()
    const source = entry()
    store.conflicts = [source]
    const restoring = store.restore(source, id)
    await vi.waitFor(() => expect(mocks.fetch).toHaveBeenCalledOnce())
    useSettingsStore().settings = { workspace_path: '/different-workspace' } as any
    useSettingsStore().workspaceSelectionRevision += 1
    resolve(draft())
    await expect(restoring).rejects.toThrow('workspace changed')
    expect(mocks.put).not.toHaveBeenCalled()
    expect(mocks.clear).not.toHaveBeenCalled()
    expect(store.conflicts).toEqual([source])
  })

  it('retains recovery when workspace selection changes while its acknowledgment is pending', async () => {
    let resolve!: (value: WorkflowFormatStatus) => void
    mocks.ack.mockReturnValueOnce(new Promise<WorkflowFormatStatus>(accept => { resolve = accept }))
    const source = { ...entry(), workspace_path: '/workspace', identity_generation: 3 }
    const store = useWorkflowRecoveryStore()
    await store.reconcile(receipt())
    store.conflicts = [source]
    const restoring = store.restore(source, id)
    await vi.waitFor(() => expect(mocks.ack).toHaveBeenCalledOnce())
    useSettingsStore().workspaceSelectionRevision += 1
    resolve({ notices: [], workspace_path: '/workspace', identity_migrations: [] })
    await expect(restoring).rejects.toThrow('workspace changed')
    expect(mocks.clear).not.toHaveBeenCalled()
    expect(store.conflicts).toEqual([source])
  })

  it('removes only the accepted source when copied workspaces share a workflow UUID', async () => {
    const first = { ...entry(), name: id, workspace_path: '/first', identity_generation: 0, recovery_key: '["/first","uuid",0]' }
    const second = { ...first, workspace_path: '/second', recovery_key: '["/second","uuid",0]' }
    const store = useWorkflowRecoveryStore()
    store.conflicts = [first, second]
    await store.restore(first, id)
    expect(mocks.clear).toHaveBeenCalledWith(first)
    expect(store.conflicts).toEqual([second])
  })
})
