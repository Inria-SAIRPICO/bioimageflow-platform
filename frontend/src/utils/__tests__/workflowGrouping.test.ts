import { describe, expect, it } from 'vitest'
import { decodeEndpointHandle, encodeEndpointHandle } from '../endpointHandles'
import { groupIntoWorkflow } from '../workflowGrouping'

function toolNode(id: string, x: number) {
  return {
    id,
    type: 'tool',
    position: { x, y: 0 },
    data: {
      nodeType: 'tool', name: id, toolName: 'tool', parameters: {}, resources: {},
      output_templates: {}, enabled: true, collapsed: false, tool: null,
    },
  }
}

describe('groupIntoWorkflow', () => {
  it('preserves detached branches and creates stable field and DataFrame ports', () => {
    const nodes = [toolNode('before', 0), toolNode('a', 100), toolNode('detached', 150), toolNode('after', 300)]
    const edges = [
      {
        id: 'field-in', source: 'before', target: 'a', type: 'column',
        sourceHandle: encodeEndpointHandle({ kind: 'tool-output', name: 'image' }),
        targetHandle: encodeEndpointHandle({ kind: 'tool-input', name: 'image' }),
      },
      {
        id: 'table-out', source: 'a', target: 'after', type: 'dataframe',
        sourceHandle: encodeEndpointHandle({ kind: 'dataframe-output' }),
        targetHandle: encodeEndpointHandle({ kind: 'dataframe-position', index: 0 }),
      },
    ]

    const result = groupIntoWorkflow({
      nodes,
      edges,
      selectedNodeIds: new Set(['a', 'detached']),
      workflowNodeId: 'group',
      workflowNodeName: 'Grouped',
    })

    const workflow = result.workflowNode.data!.workflow
    expect(workflow.nodes.map((node: { id: string }) => node.id)).toEqual(['a', 'detached'])
    expect(workflow.interface.inputs).toHaveLength(1)
    expect(workflow.interface.inputs[0].targets[0]).toEqual({
      node: 'a', port: { kind: 'field', name: 'image' },
    })
    expect(decodeEndpointHandle(result.edges[0].targetHandle!)).toEqual({
      kind: 'workflow-input', id: workflow.interface.inputs[0].id,
    })
    expect(decodeEndpointHandle(result.edges[1].sourceHandle!)).toEqual({ kind: 'dataframe-output' })
  })

  it('supports a zero-interface selection', () => {
    const result = groupIntoWorkflow({
      nodes: [toolNode('only', 0)], edges: [], selectedNodeIds: new Set(['only']),
      workflowNodeId: 'group', workflowNodeName: 'Grouped',
    })
    expect(result.workflowNode.data!.workflow.interface).toEqual({ inputs: [], outputs: [] })
  })

  it('publishes an incoming positional DataFrame and preserves exact DataFrame routes', () => {
    const nodes = [
      toolNode('before', 0),
      toolNode('first', 100),
      toolNode('second', 200),
      toolNode('after', 300),
    ]
    const edges = [
      {
        id: 'table-in', source: 'before', target: 'first', type: 'dataframe',
        sourceHandle: encodeEndpointHandle({ kind: 'dataframe-output' }),
        targetHandle: encodeEndpointHandle({ kind: 'dataframe-position', index: 0 }),
      },
      {
        id: 'table-internal', source: 'first', target: 'second', type: 'dataframe',
        sourceHandle: encodeEndpointHandle({ kind: 'dataframe-output' }),
        targetHandle: encodeEndpointHandle({ kind: 'dataframe-position', index: 0 }),
      },
      {
        id: 'table-out', source: 'second', target: 'after', type: 'dataframe',
        sourceHandle: encodeEndpointHandle({ kind: 'dataframe-output' }),
        targetHandle: encodeEndpointHandle({ kind: 'dataframe-position', index: 0 }),
      },
    ]

    const result = groupIntoWorkflow({
      nodes,
      edges,
      selectedNodeIds: new Set(['first', 'second']),
      workflowNodeId: 'group',
      workflowNodeName: 'Grouped',
    })

    expect(result.workflowNode.data!.workflow.interface.inputs).toEqual([{
      id: 'input-table-in',
      name: 'first.table_0',
      kind: 'dataframe',
      schema: { type: 'DataFrame' },
      default: null,
      targets: [{ node: 'first', port: { kind: 'positional', index: 0 } }],
    }])
    expect(result.workflowNode.data!.workflow.edges).toEqual([{
      type: 'dataframe',
      id: 'table-internal',
      source_node: 'first',
      target_node: 'second',
      target_position: 0,
      target_input: null,
    }])
    expect(result.edges).toEqual([{
      ...edges[0],
      target: 'group',
      targetHandle: encodeEndpointHandle({ kind: 'workflow-input', id: 'input-table-in' }),
    }, {
      ...edges[2],
      source: 'group',
    }])
  })
})
