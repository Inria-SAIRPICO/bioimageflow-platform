import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError } from 'axios'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    put: vi.fn(),
  },
}))

import { api } from '@/api/client'
import { useWorkflowDraftStore } from '../workflowDraft'
import type { GraphState } from '@/api/types'

const emptyGraph: GraphState = {
  nodes: [],
  edges: [],
}

function draft(revision: number, graph: GraphState = emptyGraph) {
  return {
    draft_version: 1,
    workflow_id: 'wf',
    base_saved_revision: 'sha256:abc',
    draft_revision: revision,
    updated_at: '2026-05-21T12:00:00Z',
    updated_by: 'frontend',
    dirty_against_saved: revision > 0,
    graph,
    validation: { valid: true, node_statuses: {}, errors: [] },
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

  it('flushes pending saves with the tracked expected revision', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: draft(1) })
    vi.mocked(api.put).mockResolvedValueOnce({ data: draft(2) })

    const store = useWorkflowDraftStore()
    await store.loadDraft('wf')
    store.scheduleSave('wf', emptyGraph)
    await store.flush()

    expect(api.put).toHaveBeenCalledWith('/api/v1/workflow-drafts/wf', {
      graph: emptyGraph,
      expected_revision: 1,
      updated_by: 'frontend',
    })
    expect(store.currentDraftRevision).toBe(2)
  })

  it('marks stale state on revision conflict without retrying blindly', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: draft(1) })
    vi.mocked(api.put).mockRejectedValueOnce(
      new AxiosError(
        'conflict',
        'ERR_BAD_REQUEST',
        undefined,
        undefined,
        {
          status: 409,
          statusText: 'Conflict',
          headers: {},
          config: {} as any,
          data: { current_revision: 4 },
        },
      ),
    )

    const store = useWorkflowDraftStore()
    await store.loadDraft('wf')
    store.scheduleSave('wf', emptyGraph)
    await store.flush()

    expect(store.remoteAvailableRevision).toBe(4)
    expect(store.isStale).toBe(true)
    expect(api.put).toHaveBeenCalledTimes(1)
  })
})
