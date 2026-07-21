import { describe, expect, it } from 'vitest'
import { encodeEndpointHandle } from '@/utils/endpointHandles'
import { emptyGraph } from '@/sessions/graphDocument'
import { serializeGraph } from '../useGraphSync'

describe('canonical canvas serialization', () => {
  it('serializes both node discriminators and typed edge endpoints', () => {
    const child = emptyGraph('child', 'Child')
    child.interface.inputs.push({
      id: 'input-id', name: 'Input', kind: 'field', schema: null, default: null, targets: [],
    })
    const graph = serializeGraph({
      name: 'root',
      display_name: 'Root',
      interface: { inputs: [], outputs: [] },
      nodes: [
        {
          id: 'tool', type: 'tool', position: { x: 0, y: 0 },
          data: {
            nodeType: 'tool', name: 'Tool', toolName: 'tool', parameters: {},
            resources: {}, output_templates: {}, enabled: true, collapsed: false,
          },
        },
        {
          id: 'workflow', type: 'workflow', position: { x: 100, y: 0 },
          data: {
            nodeType: 'workflow', name: 'Workflow', workflow: child, bindings: {},
            source: null, resources: {}, enabled: true, collapsed: false,
          },
        },
      ],
      edges: [{
        id: 'edge', type: 'column', source: 'tool', target: 'workflow',
        sourceHandle: encodeEndpointHandle({ kind: 'tool-output', name: 'result' }),
        targetHandle: encodeEndpointHandle({ kind: 'workflow-input', id: 'input-id' }),
      }],
    })

    expect(graph.nodes.map(node => node.type)).toEqual(['tool', 'workflow'])
    expect(graph.edges).toEqual([{
      id: 'edge', type: 'column', source_node: 'tool', target_node: 'workflow',
      source_output: 'result', target_input: 'input-id',
    }])
    expect(graph.nodes[1]).not.toHaveProperty('tool_name')
  })

  it('rejects canvas nodes without an explicit discriminator', () => {
    expect(() => serializeGraph({ nodes: [{ id: 'unknown', data: {} }], edges: [] }))
      .toThrow(/discriminator/)
  })

  it('uses the platform discriminator while Vue Flow normalises its renderer type', () => {
    const graph = serializeGraph({
      nodes: [{
        id: 'cross_join_1',
        position: { x: 0, y: 0 },
        data: {
          nodeType: 'tool',
          name: 'Cross join',
          toolName: 'CrossJoin',
          parameters: {},
        },
      }],
      edges: [],
    })

    expect(graph.nodes[0]).toMatchObject({
      type: 'tool',
      id: 'cross_join_1',
      tool_name: 'CrossJoin',
    })
  })
})
