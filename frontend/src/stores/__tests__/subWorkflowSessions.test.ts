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
