import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { makeGraph, makeValidationResult } from '@/test-utils/graphFixtures'
import { openNestedWorkflowSnapshot } from '@/api/nestedWorkflowSnapshots'
import { useNestedWorkflowSessionsStore } from '../nestedWorkflowSessions'

vi.mock('@/api/nestedWorkflowSnapshots', () => ({
  openNestedWorkflowSnapshot: vi.fn(),
  deleteNestedWorkflowSnapshot: vi.fn(),
}))

describe('nested workflow sessions', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('keeps one canonical child graph for draft and parent application', async () => {
    const graph = makeGraph({ name: 'child', display_name: 'Child' })
    vi.mocked(openNestedWorkflowSnapshot).mockResolvedValue({
      snapshot_version: 1,
      session_id: '00000000-0000-4000-8000-000000000001',
      owner: { kind: 'root', canvas_id: 'root', workflow_id: 'parent' },
      parent_node_id: 'child-node',
      snapshot_revision: 1,
      updated_at: '2026-07-20T00:00:00Z',
      graph,
      validation: makeValidationResult(),
    })
    const store = useNestedWorkflowSessionsStore()
    const session = await store.openDurableSession({
      owner: { kind: 'root', canvas_id: 'root', workflow_id: 'parent' },
      parentCanvasId: 'root', parentWorkflowName: 'parent',
      parentNodeId: 'child-node', parentNodeName: 'Child', graph,
    })
    expect(session.draft).toEqual(graph)
  })
})
