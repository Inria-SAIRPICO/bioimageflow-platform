import { describe, expect, it } from 'vitest'
import { graphStateToVueFlow } from '../workflowGraph'
import type { GraphState, ToolMetadata } from '@/api/types'

function makeProcessingTool(overrides: Partial<ToolMetadata> = {}): ToolMetadata {
  return {
    name: 'spot_detection',
    display_name: 'Spot Detection',
    package: 'core',
    package_version: '1.0.0',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    documentation: '',
    tags: [],
    categories: [],
    inputs: {
      image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default' },
      sigma: { type: 'float', required: false, nullable: false, connectable: 'not_by_default', default: 1.0 },
    },
    outputs: {
      result: { type: 'ImageFile' },
      sigma: { type: 'float' },
    },
    environment: null,
    ...overrides,
  }
}

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

  it('pins optional connectable body inputs that have loaded column_ref edges', () => {
    const tool = makeProcessingTool()
    const graph: GraphState = {
      nodes: [
        {
          id: 'source',
          name: 'Source',
          tool_name: 'spot_detection',
          position: [0, 0],
          parameters: {},
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        },
        {
          id: 'target',
          name: 'Target',
          tool_name: 'spot_detection',
          position: [100, 0],
          parameters: {},
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        },
      ],
      edges: [{
        id: 'edge-sigma',
        type: 'column_ref',
        source_node: 'source',
        target_node: 'target',
        source_output: 'sigma',
        target_input: 'sigma',
      }],
    }

    const result = graphStateToVueFlow(graph, () => tool)
    const target = result.nodes.find((node) => node.id === 'target')

    expect(target?.data.connectedInputs.sigma).toBe('source.sigma')
    expect(target?.data.pinnedInputs.sigma).toBe(true)
  })
})
