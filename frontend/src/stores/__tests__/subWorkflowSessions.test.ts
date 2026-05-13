import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useSubWorkflowSessionsStore } from '../subWorkflowSessions'
import type { GraphState } from '@/api/types'

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

  it('assigns each sub-workflow session an isolated draft identity and sync metadata', () => {
    const store = useSubWorkflowSessionsStore()
    const rootA = store.openSession({
      parentWorkflowName: 'parent',
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: graph('internal_1'),
    })
    const rootB = store.openSession({
      parentWorkflowName: 'parent',
      parentNodeId: 'sub_2',
      parentNodeName: 'Sub 2',
      graph: graph('internal_2'),
    })

    expect(rootA.draft_id).toBe('sub-workflow:parent:sub_1')
    expect(rootB.draft_id).toBe('sub-workflow:parent:sub_2')
    expect(rootA.revision).toBe(0)
    expect(rootA.client_seq).toBe(0)
    expect(rootA.validation_result).toBeNull()
    expect(rootA.dirty).toBe(false)
    expect(rootA.pending_sync).toBe(false)
  })

  it('tracks sub-workflow draft revision state independently from saved parent snapshots', () => {
    const store = useSubWorkflowSessionsStore()
    const session = store.openSession({
      parentWorkflowName: 'parent',
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: graph('internal_1'),
    })

    store.updateDraftSyncState(session.id, {
      revision: 3,
      client_seq: 2,
      validation_result: { valid: true, node_statuses: {}, errors: [] },
      dirty: true,
      pending_sync: false,
    })

    const updated = store.sessionById(session.id)
    expect(updated?.revision).toBe(3)
    expect(updated?.client_seq).toBe(2)
    expect(updated?.validation_result?.valid).toBe(true)
    expect(updated?.dirty).toBe(true)
    expect(updated?.savedSnapshot.nodes[0].id).toBe('internal_1')
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
})
