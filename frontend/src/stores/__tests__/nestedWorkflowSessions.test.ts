import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { makeGraph, makeValidationResult } from '@/test-utils/graphFixtures'
import { nestedWorkflowApplyCoordinator } from '@/sessions/nestedWorkflowApplyCoordinator'
import { openNestedWorkflowSnapshot } from '@/api/nestedWorkflowSnapshots'
import { useNestedWorkflowSessionsStore } from '../nestedWorkflowSessions'

vi.mock('@/api/nestedWorkflowSnapshots', () => ({
  openNestedWorkflowSnapshot: vi.fn(),
  deleteNestedWorkflowSnapshot: vi.fn(),
}))

describe('nested workflow sessions', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('scopes open-editor refusal to the exact root canvas, workflow and target node', async () => {
    const graph = makeGraph({ name: 'child' })
    const owner = { kind: 'root' as const, canvas_id: 'root', workflow_id: 'parent' }
    vi.mocked(openNestedWorkflowSnapshot).mockResolvedValue({
      snapshot_version: 1, session_id: 'root-child', owner,
      parent_node_id: 'child-node', snapshot_revision: 1,
      updated_at: '2026-07-20T00:00:00Z', graph, validation: makeValidationResult(),
    })
    const store = useNestedWorkflowSessionsStore()
    const session = await store.openDurableSession({
      owner, parentCanvasId: 'root', parentWorkflowName: 'parent',
      parentNodeId: 'child-node', parentNodeName: 'Child', graph,
    })

    // A clean editor also owns its subtree; refusal is not a dirty-state check.
    expect(store.isDirty(session.id)).toBe(false)
    expect(store.hasOpenEditorForNode(owner, 'child-node')).toBe(true)
    expect(store.hasOpenEditorForNode(owner, 'sibling-node')).toBe(false)
    expect(store.hasOpenEditorForNode({ ...owner, canvas_id: 'other-root' }, 'child-node')).toBe(false)
    expect(store.hasOpenEditorForNode({ ...owner, workflow_id: 'other-workflow' }, 'child-node')).toBe(false)
    expect(store.hasOpenEditorForNode({ kind: 'nested', session_id: 'root' }, 'child-node')).toBe(false)
    store.closeSession(session.id)
    expect(store.hasOpenEditorForNode(owner, 'child-node')).toBe(false)
  })

  it('keeps descendant editor lookup within its exact private parent session', async () => {
    const graph = makeGraph({ name: 'grandchild' })
    const owner = { kind: 'nested' as const, session_id: 'private-parent' }
    vi.mocked(openNestedWorkflowSnapshot).mockResolvedValue({
      snapshot_version: 1, session_id: 'private-child', owner,
      parent_node_id: 'child-node', snapshot_revision: 1,
      updated_at: '2026-07-20T00:00:00Z', graph, validation: makeValidationResult(),
    })
    const store = useNestedWorkflowSessionsStore()
    const session = await store.openDurableSession({
      owner, parentCanvasId: 'nested:private-parent', parentWorkflowName: 'parent',
      parentNodeId: 'child-node', parentNodeName: 'Child', graph,
    })

    expect(store.hasOpenEditorForNode(owner, 'child-node')).toBe(true)
    expect(store.hasOpenEditorForNode(owner, 'sibling-node')).toBe(false)
    expect(store.hasOpenEditorForNode({ kind: 'nested', session_id: 'other-parent' }, 'child-node')).toBe(false)
    store.closeSession(session.id)
    expect(store.hasOpenEditorForNode(owner, 'child-node')).toBe(false)
  })

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

  it('acknowledges applied A without overwriting newer accepted private B', async () => {
    const graphA = makeGraph({ name: 'a', display_name: 'A' })
    const graphB = makeGraph({ name: 'b', display_name: 'B' })
    vi.mocked(openNestedWorkflowSnapshot).mockResolvedValue({
      snapshot_version: 1,
      session_id: '00000000-0000-4000-8000-000000000002',
      owner: { kind: 'root', canvas_id: 'root', workflow_id: 'parent' },
      parent_node_id: 'child-node', snapshot_revision: 2,
      updated_at: '2026-07-20T00:00:00Z', graph: graphA,
      validation: makeValidationResult(),
    })
    const store = useNestedWorkflowSessionsStore()
    const session = await store.openDurableSession({
      owner: { kind: 'root', canvas_id: 'root', workflow_id: 'parent' },
      parentCanvasId: 'root', parentWorkflowName: 'parent',
      parentNodeId: 'child-node', parentNodeName: 'Child', graph: graphA,
    })
    store.updateDraft(session.id, graphB)
    store.acceptSnapshot(session.id, {
      snapshot_version: 1,
      session_id: session.id,
      owner: session.owner,
      parent_node_id: session.parentNodeId,
      snapshot_revision: 3,
      updated_at: '2026-07-20T00:00:01Z', graph: graphB,
      validation: makeValidationResult(),
    })

    store.acknowledgeApplied(session.id, graphA, 2, makeValidationResult())

    expect(session.savedSnapshot).toEqual(graphA)
    expect(session.draft).toEqual(graphB)
    expect(session.acceptedSnapshot).toEqual(graphB)
    expect(session.snapshotRevision).toBe(3)
    expect(store.isDirty(session.id)).toBe(true)
  })

  it('clears retained apply state only when the session is finally closed', async () => {
    const graph = makeGraph({ name: 'close' })
    vi.mocked(openNestedWorkflowSnapshot).mockResolvedValue({
      snapshot_version: 1,
      session_id: '00000000-0000-4000-8000-000000000003',
      owner: { kind: 'root', canvas_id: 'root', workflow_id: 'parent' },
      parent_node_id: 'child-node', snapshot_revision: 1,
      updated_at: '2026-07-20T00:00:00Z', graph,
      validation: makeValidationResult(),
    })
    const store = useNestedWorkflowSessionsStore()
    const session = await store.openDurableSession({
      owner: { kind: 'root', canvas_id: 'root', workflow_id: 'parent' },
      parentCanvasId: 'root', parentWorkflowName: 'parent',
      parentNodeId: 'child-node', parentNodeName: 'Child', graph,
    })
    const clear = vi.spyOn(nestedWorkflowApplyCoordinator, 'clear')

    store.closeSession(session.id)

    expect(clear).toHaveBeenCalledOnce()
    expect(clear).toHaveBeenCalledWith(session.id)
    expect(store.sessionById(session.id)).toBeUndefined()
  })
})
