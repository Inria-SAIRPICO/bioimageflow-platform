import { describe, expect, it } from 'vitest'
import { graphStateToVueFlow } from '../workflowGraph'
import type { GraphState } from '@/api/types'

describe('graphStateToVueFlow', () => {
  it('preserves editable sub-workflow node data on load', () => {
    const graph: GraphState = {
      nodes: [{
        id: 'outer',
        name: 'Outer',
        tool_name: '__sub_workflow__',
        position: [10, 20],
        parameters: { image: '/tmp/input.tif' },
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
        sub_workflow: {
          nodes: [{
            id: 'inner',
            name: 'Inner',
            tool_name: 'TProcTool',
            position: [1, 2],
            parameters: { diameter: 7 },
            resources: {},
            output_templates: {},
            enabled: true,
            collapsed: false,
          }],
          edges: [],
        },
        published_inputs: [{
          name: 'image',
          internal_node_id: 'inner',
          internal_field: 'input_image',
          kind: 'input',
          schema: { type: 'Path' },
          default: null,
        }],
        published_outputs: [{
          name: 'mask',
          internal_node_id: 'inner',
          internal_output: 'mask',
          schema: { type: 'Path' },
        }],
        sub_workflow_readonly_reason: null,
      }],
      edges: [],
    }

    const result = graphStateToVueFlow(graph, () => undefined)

    expect(result.nodes[0]).toMatchObject({
      id: 'outer',
      type: 'sub_workflow',
      data: {
        toolName: '__sub_workflow__',
        sub_workflow: graph.nodes[0].sub_workflow,
        published_inputs: graph.nodes[0].published_inputs,
        published_outputs: graph.nodes[0].published_outputs,
        sub_workflow_readonly_reason: null,
      },
    })
  })
})
