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

  it('declares the optional viewer fields of the persisted document', () => {
    const child = emptyGraph('child', 'Child')
    child.nodes.push({
      type: 'tool', id: 'child_tool', name: 'Child tool', tool_name: 'tool',
      position: [0, 0], parameters: {}, enabled: true, collapsed: false,
    })
    child.interface.outputs.push({
      id: 'child-output', name: 'Child output', schema: { type: 'ImageFile' },
      source: { node: 'child_tool', column: 'result' },
    })
    const graph = serializeGraph({
      name: 'root',
      interface: {
        inputs: [],
        outputs: [
          {
            id: 'plain-output', name: 'Plain output', schema: { type: 'ImageFile' },
            source: { node: 'tool', column: 'result' },
          },
          {
            id: 'declared-output', name: 'Declared output', schema: { type: 'ImageFile' },
            source: { node: 'tool', column: 'result' },
            viewer_addition: { napari: null },
          },
        ],
      },
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
            viewerAdditions: { result: { napari: null } },
          },
        },
      ],
      edges: [],
    })

    expect(graph.interface.outputs).toEqual([
      {
        id: 'plain-output', name: 'Plain output', schema: { type: 'ImageFile' },
        source: { node: 'tool', column: 'result' },
        viewer_addition: null,
      },
      {
        id: 'declared-output', name: 'Declared output', schema: { type: 'ImageFile' },
        source: { node: 'tool', column: 'result' },
        viewer_addition: { napari: null },
      },
    ])
    expect(graph.nodes[0]).toMatchObject({ viewer_additions: {} })
    expect(graph.nodes[1]).toMatchObject({
      viewer_additions: { result: { napari: null } },
      workflow: {
        nodes: [{ viewer_additions: {} }],
        interface: {
          outputs: [{
            id: 'child-output', name: 'Child output', schema: { type: 'ImageFile' },
            source: { node: 'child_tool', column: 'result' },
            viewer_addition: null,
          }],
        },
      },
    })
  })

  it('rejects canvas nodes without an explicit discriminator', () => {
    expect(() => serializeGraph({ nodes: [{ id: 'unknown', data: {} }], edges: [] }))
      .toThrow(/discriminator/)
  })

  it('rejects a renderer-only discriminator', () => {
    expect(() => serializeGraph({
      nodes: [{
        id: 'cross_join_1',
        type: 'tool',
        position: { x: 0, y: 0 },
        data: {
          name: 'Cross join',
          toolName: 'CrossJoin',
          parameters: {},
        },
      }],
      edges: [],
    })).toThrow(/cross_join_1 has no valid discriminator/)
  })
})
