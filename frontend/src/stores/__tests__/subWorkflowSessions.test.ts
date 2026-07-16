import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useSubWorkflowSessionsStore } from '../subWorkflowSessions'
import type { GraphState } from '@/api/types'

const snapshotApiMocks = vi.hoisted(() => ({
  open: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/nestedWorkflowSnapshots', () => ({
  openNestedWorkflowSnapshot: snapshotApiMocks.open,
  deleteNestedWorkflowSnapshot: snapshotApiMocks.delete,
}))

function graph(nodeId: string): GraphState {
  return {
    nodes: [{
      id: nodeId,
      name: nodeId,
      tool_name: 'tool',
      position: [0, 0],
      parameters: {},
      resources: {},
      output_templates: {},
      enabled: true,
      collapsed: false,
    }],
    edges: [],
  }
}

describe('useSubWorkflowSessionsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    snapshotApiMocks.open.mockReset()
    snapshotApiMocks.delete.mockReset()
  })

  it('opens a deep-cloned draft so parent graph data is unchanged until save', () => {
    const store = useSubWorkflowSessionsStore()
    const parentGraph = graph('internal_1')

    const session = store.openSession({
      parentWorkflowName: 'parent',
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: parentGraph,
    })

    session.draft.nodes[0].name = 'changed'

    expect(parentGraph.nodes[0].name).toBe('internal_1')
    expect(store.isDirty(session.id)).toBe(true)
  })

  it('returns a cloned draft on save and marks the session clean', () => {
    const store = useSubWorkflowSessionsStore()
    const session = store.openSession({
      parentWorkflowName: 'parent',
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: graph('internal_1'),
    })
    session.draft.nodes[0].name = 'changed'

    const saved = store.saveSession(session.id)
    saved.graph.nodes[0].name = 'mutated after save'

    expect(store.sessionById(session.id)?.draft.nodes[0].name).toBe('changed')
    expect(store.isDirty(session.id)).toBe(false)
  })

  it('tracks published interface edits as dirty and includes them in save payload', () => {
    const store = useSubWorkflowSessionsStore()
    const session = store.openSession({
      parentWorkflowName: 'parent',
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: graph('internal_1'),
      published_inputs: [{
        name: 'image',
        internal_node_id: 'internal_1',
        internal_field: 'input_image',
        kind: 'input',
        schema: { type: 'Path' },
        default: null,
      }],
      published_outputs: [],
    })

    session.published_inputs[0].name = 'input_folder'

    expect(store.isDirty(session.id)).toBe(true)
    expect(store.dirtySessionIds).toEqual([session.id])

    const saved = store.saveSession(session.id)
    saved.published_inputs[0].name = 'changed-after-save'

    expect(saved.graph.nodes[0].id).toBe('internal_1')
    expect(store.sessionById(session.id)?.published_inputs[0].name).toBe('input_folder')
    expect(store.isDirty(session.id)).toBe(false)
  })

  it('updates a draft without mutating the saved snapshot', () => {
    const store = useSubWorkflowSessionsStore()
    const session = store.openSession({
      parentWorkflowName: 'parent',
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: graph('internal_1'),
    })

    store.updateDraft(session.id, graph('internal_2'))

    expect(store.sessionById(session.id)?.draft.nodes[0].id).toBe('internal_2')
    expect(store.sessionById(session.id)?.savedSnapshot.nodes[0].id).toBe('internal_1')
    expect(store.isDirty(session.id)).toBe(true)
  })

  it('refuses to open readonly class-based sub-workflows', () => {
    const store = useSubWorkflowSessionsStore()

    expect(() => store.openSession({
      parentWorkflowName: 'parent',
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: graph('internal_1'),
      readonlyReason: 'Loaded from a Python SubWorkflow class',
    })).toThrow('Loaded from a Python SubWorkflow class')
  })

  it('hydrates a recovered private snapshot without changing its parent baseline', async () => {
    const store = useSubWorkflowSessionsStore()
    const parentGraph = graph('parent_version')
    const recoveredGraph = {
      ...graph('recovered_version'),
      published_inputs: [{
        name: 'source',
        internal_node_id: 'recovered_version',
        internal_field: 'image',
        kind: 'input' as const,
        schema: { type: 'Path' },
        default: null,
      }],
      published_outputs: [],
    }
    snapshotApiMocks.open.mockResolvedValue({
      snapshot_version: 1,
      session_id: 'f16fd9d4-18e5-4d73-a9df-b7675ef44c9e',
      owner: { kind: 'root', canvas_id: 'canvas', workflow_id: null },
      parent_node_id: 'sub_1',
      snapshot_revision: 7,
      updated_at: '2026-07-16T00:00:00Z',
      graph: recoveredGraph,
      validation: { valid: true, node_statuses: {}, errors: [] },
    })

    const session = await store.openDurableSession({
      owner: { kind: 'root', canvas_id: 'canvas', workflow_id: null },
      parentCanvasId: 'canvas',
      parentWorkflowName: null,
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: parentGraph,
    })
    const reopened = await store.openDurableSession({
      owner: { kind: 'root', canvas_id: 'canvas', workflow_id: null },
      parentCanvasId: 'canvas',
      parentWorkflowName: null,
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: parentGraph,
    })

    expect(session.id).toBe('f16fd9d4-18e5-4d73-a9df-b7675ef44c9e')
    expect(session.draft).toEqual(recoveredGraph)
    expect(session.savedSnapshot).toEqual(expect.objectContaining({
      nodes: [expect.objectContaining({ id: 'parent_version' })],
    }))
    expect(store.isDirty(session.id)).toBe(true)
    expect(parentGraph.nodes[0]!.id).toBe('parent_version')
    expect(reopened).toBe(session)
    expect(snapshotApiMocks.open).toHaveBeenCalledTimes(1)

    store.updateDraft(session.id, graph('newer_local_version'))
    expect(store.snapshotForSession(session.id).graph.nodes[0]!.id)
      .toBe('recovered_version')
    expect(session.draft.nodes[0]!.id).toBe('newer_local_version')
  })

  it('revision-checks durable deletion before dropping local session state', async () => {
    const store = useSubWorkflowSessionsStore()
    snapshotApiMocks.open.mockResolvedValue({
      snapshot_version: 1,
      session_id: 'f16fd9d4-18e5-4d73-a9df-b7675ef44c9e',
      owner: { kind: 'root', canvas_id: 'canvas', workflow_id: null },
      parent_node_id: 'sub_1',
      snapshot_revision: 3,
      updated_at: '2026-07-16T00:00:00Z',
      graph: {
        ...graph('inner'),
        published_inputs: [],
        published_outputs: [],
        nodes: [{
          ...graph('inner').nodes[0]!,
          sub_workflow: null,
          published_inputs: [],
          published_outputs: [],
          sub_workflow_readonly_reason: null,
        }],
      },
      validation: { valid: true, node_statuses: {}, errors: [] },
    })
    snapshotApiMocks.delete.mockResolvedValue(undefined)
    const session = await store.openDurableSession({
      owner: { kind: 'root', canvas_id: 'canvas', workflow_id: null },
      parentCanvasId: 'canvas',
      parentWorkflowName: null,
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: graph('inner'),
    })

    expect(store.isDirty(session.id)).toBe(false)

    await store.deleteDurableSession(session.id)

    expect(snapshotApiMocks.delete).toHaveBeenCalledWith(session.id, 3)
    expect(store.sessionById(session.id)).toBeUndefined()
  })
})
