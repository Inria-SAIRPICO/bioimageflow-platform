import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    put: vi.fn(),
  },
}))

import { api } from '@/api/client'
import { useWorkflowDraftStore, type WorkflowDraftChangedMessage } from '../workflowDraft'
import type { GraphState } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import { makeGraph } from '@/test-utils/graphFixtures'

const emptyGraph: GraphState = makeGraph()

function draft(
  revision: number,
  graph: GraphState = emptyGraph,
  workflowId = 'wf',
): WorkflowDraftResponse {
  return {
    draft_version: 1,
    workflow_id: workflowId,
    base_saved_revision: 'sha256:abc',
    draft_revision: revision,
    updated_at: '2026-05-21T12:00:00Z',
    updated_by: 'frontend',
    dirty_against_saved: revision > 0,
    graph,
    validation: { valid: true, node_statuses: {}, errors: [] },
  }
}

function changed(
  revision: number,
  overrides: Partial<WorkflowDraftChangedMessage> = {},
): WorkflowDraftChangedMessage {
  return {
    type: 'workflow_draft_changed',
    workflow_id: 'wf',
    draft_revision: revision,
    updated_by: 'agent',
    updated_at: '2026-05-21T12:05:00Z',
    dirty_against_saved: true,
    ...overrides,
  }
}

describe('workflow draft store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useRealTimers()
    vi.mocked(api.get).mockReset()
    vi.mocked(api.put).mockReset()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  it('loads the current draft revision from the backend', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: draft(3) })

    const store = useWorkflowDraftStore()
    const response = await store.loadDraft('wf')

    expect(response.draft_revision).toBe(3)
    expect(store.currentDraftRevision).toBe(3)
    expect(store.appliedDraftRevision).toBe(3)
    expect(api.get).toHaveBeenCalledWith('/api/v1/workflow-drafts/wf')
  })

  it('notes newer remote draft changes with metadata without applying them', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: draft(3) })

    const store = useWorkflowDraftStore()
    await store.loadDraft('wf')
    store.noteRemoteChange(changed(4, {
      updated_by: 'system',
      updated_at: '2026-05-21T12:06:00Z',
      dirty_against_saved: false,
    }))

    expect(store.remoteAvailableRevision).toBe(4)
    expect(store.remoteUpdatedBy).toBe('system')
    expect(store.remoteUpdatedAt).toBe('2026-05-21T12:06:00Z')
    expect(store.remoteDirtyAgainstSaved).toBe(false)
    expect(store.appliedDraftRevision).toBe(3)
    expect(store.currentDraftRevision).toBe(3)
    expect(store.isStale).toBe(true)
  })

  it('restores a retained remote notice when its workflow becomes tracked', () => {
    const store = useWorkflowDraftStore()
    store.reset('workflow-a')

    store.noteRemoteChange(changed(5, {
      workflow_id: 'workflow-b',
      updated_by: 'system',
      updated_at: '2026-05-21T12:09:00Z',
      dirty_against_saved: false,
    }))

    expect(store.workflowId).toBe('workflow-a')
    expect(store.remoteAvailableRevision).toBeNull()

    store.trackWorkflow('workflow-b')

    expect(store.remoteAvailableRevision).toBe(5)
    expect(store.remoteUpdatedBy).toBe('system')
    expect(store.remoteUpdatedAt).toBe('2026-05-21T12:09:00Z')
    expect(store.remoteDirtyAgainstSaved).toBe(false)
  })

  it('keeps workflow notices independent when acknowledging an inactive workflow', () => {
    const store = useWorkflowDraftStore()
    store.reset('workflow-a')
    store.noteRemoteChange(changed(4, { workflow_id: 'workflow-a' }))
    store.noteRemoteChange(changed(6, { workflow_id: 'workflow-b' }))

    store.acknowledgeAcceptedDraft(draft(6, emptyGraph, 'workflow-b'))

    expect(store.workflowId).toBe('workflow-a')
    expect(store.appliedDraftRevision).toBeNull()
    expect(store.remoteAvailableRevision).toBe(4)

    store.trackWorkflow('workflow-b')
    expect(store.currentDraftRevision).toBe(6)
    expect(store.appliedDraftRevision).toBe(6)
    expect(store.remoteAvailableRevision).toBeNull()

    store.trackWorkflow('workflow-a')
    expect(store.appliedDraftRevision).toBeNull()
    expect(store.remoteAvailableRevision).toBe(4)
  })

  it('clears every retained workflow state on reset', () => {
    const store = useWorkflowDraftStore()
    store.reset('workflow-a')
    store.noteRemoteChange(changed(5, { workflow_id: 'workflow-b' }))

    store.reset('workflow-a')
    store.trackWorkflow('workflow-b')

    expect(store.currentDraftRevision).toBeNull()
    expect(store.appliedDraftRevision).toBeNull()
    expect(store.remoteAvailableRevision).toBeNull()
  })

  it('does not project inactive-workflow or already-known notices', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: draft(3) })

    const store = useWorkflowDraftStore()
    await store.loadDraft('wf')
    store.noteRemoteChange(changed(5, { workflow_id: 'other' }))
    store.noteRemoteChange(changed(3))

    expect(store.remoteAvailableRevision).toBeNull()
    expect(store.remoteUpdatedBy).toBeNull()
    expect(store.isStale).toBe(false)
  })

  it('tracks a newly activated workflow so its later remote events are recorded', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: draft(3) })

    const store = useWorkflowDraftStore()
    await store.loadDraft('wf')
    store.trackWorkflow('other')
    store.noteRemoteChange(changed(1, { workflow_id: 'other' }))

    expect(store.workflowId).toBe('other')
    expect(store.currentDraftRevision).toBeNull()
    expect(store.appliedDraftRevision).toBeNull()
    expect(store.remoteAvailableRevision).toBe(1)
  })

  it('ignores remote draft changes that are not newer than the recorded remote revision', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: draft(3) })

    const store = useWorkflowDraftStore()
    await store.loadDraft('wf')
    store.noteRemoteChange(changed(6, {
      updated_by: 'agent',
      updated_at: '2026-05-21T12:06:00Z',
    }))
    store.noteRemoteChange(changed(5, {
      updated_by: 'system',
      updated_at: '2026-05-21T12:07:00Z',
      dirty_against_saved: false,
    }))
    store.noteRemoteChange(changed(6, {
      updated_by: 'frontend',
      updated_at: '2026-05-21T12:08:00Z',
      dirty_against_saved: false,
    }))

    expect(store.remoteAvailableRevision).toBe(6)
    expect(store.remoteUpdatedBy).toBe('agent')
    expect(store.remoteUpdatedAt).toBe('2026-05-21T12:06:00Z')
    expect(store.remoteDirtyAgainstSaved).toBe(true)
  })

  it('acknowledges only an exact accepted write without suppressing other frontend writes', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: draft(1) })
    const store = useWorkflowDraftStore()
    await store.loadDraft('wf')
    store.noteRemoteChange(changed(2, { updated_by: 'frontend' }))

    store.acknowledgeAcceptedDraft(draft(2))

    expect(store.currentDraftRevision).toBe(2)
    expect(store.appliedDraftRevision).toBe(2)
    expect(store.remoteAvailableRevision).toBeNull()

    store.noteRemoteChange(changed(2, { updated_by: 'frontend' }))
    expect(store.remoteAvailableRevision).toBeNull()
    store.noteRemoteChange(changed(3, { updated_by: 'frontend' }))
    expect(store.remoteAvailableRevision).toBe(3)

    store.trackWorkflow('other')
    store.acknowledgeAcceptedDraft(draft(4, emptyGraph, 'wf'))
    expect(store.workflowId).toBe('other')
    expect(store.appliedDraftRevision).toBeNull()
  })

  it('preserves a newer remote revision observed before an accepted response', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: draft(1) })
    const store = useWorkflowDraftStore()
    await store.loadDraft('wf')
    store.noteRemoteChange(changed(3, { updated_by: 'agent' }))

    store.acknowledgeAcceptedDraft(draft(2))

    expect(store.currentDraftRevision).toBe(2)
    expect(store.appliedDraftRevision).toBe(2)
    expect(store.remoteAvailableRevision).toBe(3)
    expect(store.remoteUpdatedBy).toBe('agent')
  })

  it('does not reactivate a workflow when its in-flight overwrite is acknowledged', async () => {
    let resolvePut!: (value: { data: WorkflowDraftResponse }) => void
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: draft(1, emptyGraph, 'workflow-b') })
      .mockResolvedValueOnce({ data: draft(1, emptyGraph, 'workflow-b') })
    vi.mocked(api.put).mockReturnValueOnce(new Promise((resolve) => {
      resolvePut = resolve
    }))

    const store = useWorkflowDraftStore()
    await store.loadDraft('workflow-b')
    const overwrite = store.overwriteDraftWithGraph('workflow-b', emptyGraph)
    await vi.waitFor(() => expect(api.put).toHaveBeenCalledOnce())
    store.trackWorkflow('workflow-a')

    resolvePut({ data: draft(2, emptyGraph, 'workflow-b') })
    await overwrite

    expect(store.workflowId).toBe('workflow-a')
    expect(store.currentDraftRevision).toBeNull()
    store.trackWorkflow('workflow-b')
    expect(store.currentDraftRevision).toBe(2)
    expect(store.appliedDraftRevision).toBe(2)
  })

  it('forgets only the deleted workflow state before the id is reused', () => {
    const store = useWorkflowDraftStore()
    store.reset('workflow-a')
    store.noteRemoteChange(changed(4, { workflow_id: 'workflow-a' }))
    store.noteRemoteChange(changed(6, { workflow_id: 'workflow-b' }))

    store.forgetWorkflow('workflow-b')

    expect(store.workflowId).toBe('workflow-a')
    expect(store.remoteAvailableRevision).toBe(4)
    store.trackWorkflow('workflow-b')
    expect(store.currentDraftRevision).toBeNull()
    expect(store.appliedDraftRevision).toBeNull()
    expect(store.remoteAvailableRevision).toBeNull()
  })

  it('overwrites a newer remote draft with the current graph revision', async () => {
    const localGraph: GraphState = makeGraph({
      nodes: [{
        type: 'tool',
        id: 'local',
        name: 'Local',
        tool_name: 'gaussian_blur',
        position: [0, 0],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [],
    })
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: draft(3) })
      .mockResolvedValueOnce({ data: draft(4) })
    vi.mocked(api.put).mockResolvedValueOnce({ data: draft(5, localGraph) })

    const store = useWorkflowDraftStore()
    await store.loadDraft('wf')
    store.noteRemoteChange(changed(4))
    const response = await store.overwriteDraftWithGraph('wf', localGraph)

    expect(api.put).toHaveBeenCalledWith('/api/v1/workflow-drafts/wf', {
      graph: localGraph,
      expected_revision: 4,
      updated_by: 'frontend',
    })
    expect(response.draft_revision).toBe(5)
    expect(store.currentDraftRevision).toBe(5)
    expect(store.appliedDraftRevision).toBe(5)
    expect(store.remoteAvailableRevision).toBeNull()
  })

  it('can write a graph to another workflow without changing the tracked draft', async () => {
    const copyGraph: GraphState = makeGraph({
      nodes: [{
        type: 'tool',
        id: 'agent',
        name: 'Agent',
        tool_name: 'gaussian_blur',
        position: [0, 0],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [],
    })
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: draft(3) })
      .mockResolvedValueOnce({ data: draft(1, emptyGraph, 'copy') })
    vi.mocked(api.put).mockResolvedValueOnce({ data: draft(2, copyGraph, 'copy') })

    const store = useWorkflowDraftStore()
    await store.loadDraft('wf')
    await store.overwriteDraftWithGraph('copy', copyGraph, { updateTrackedDraft: false })

    expect(api.put).toHaveBeenCalledWith('/api/v1/workflow-drafts/copy', {
      graph: copyGraph,
      expected_revision: 1,
      updated_by: 'frontend',
    })
    expect(store.workflowId).toBe('wf')
    expect(store.currentDraftRevision).toBe(3)
    expect(store.appliedDraftRevision).toBe(3)
  })
})
