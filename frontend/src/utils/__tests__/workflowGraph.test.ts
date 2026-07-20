import { describe, expect, it } from 'vitest'
import type { ToolMetadata } from '@/api/types'
import { emptyGraph } from '@/sessions/graphDocument'
import { decodeEndpointHandle } from '../endpointHandles'
import { graphStateToVueFlow } from '../workflowGraph'

const tool: ToolMetadata = {
  name: 'threshold',
  display_name: 'Threshold',
  package: 'example',
  package_version: '1',
  tool_type: 'ProcessingTool',
  accepts_upstream: true,
  dynamic_outputs: false,
  dataframe_output: true,
  source_kind: 'package',
  editable: false,
  documentation: '',
  tags: [],
  categories: [],
  inputs: { image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default' } },
  outputs: { mask: { type: 'MaskPath' } },
  environment: null,
}

describe('graphStateToVueFlow', () => {
  it('renders tool and workflow nodes from their discriminators', () => {
    const child = emptyGraph('child', 'Child')
    child.interface.inputs.push({
      id: 'image-port',
      name: 'Image',
      kind: 'field',
      schema: { type: 'ImageFile' },
      default: null,
      targets: [],
    })
    child.interface.outputs.push({
      id: 'mask-port',
      name: 'Mask',
      schema: { type: 'MaskPath' },
      source: { node: 'inner', column: 'mask' },
    })
    const graph = emptyGraph('root', 'Root')
    graph.nodes = [
      {
        type: 'tool', id: 'source', name: 'Source', tool_name: 'threshold',
        position: [0, 0], parameters: {}, enabled: true, collapsed: false,
      },
      {
        type: 'workflow', id: 'child', name: 'Child', workflow: child,
        bindings: {}, source: null, position: [200, 0], enabled: true, collapsed: false,
      },
    ]
    graph.edges = [{
      type: 'column', id: 'edge', source_node: 'source', target_node: 'child',
      source_output: 'mask', target_input: 'image-port',
    }]

    const rendered = graphStateToVueFlow(graph, name => name === tool.name ? tool : undefined)

    expect(rendered.nodes.map(node => node.type)).toEqual(['tool', 'workflow'])
    expect(rendered.nodes[1].data.workflow).toEqual(child)
    expect(decodeEndpointHandle(rendered.edges[0].sourceHandle)).toEqual({
      kind: 'tool-output', name: 'mask',
    })
    expect(decodeEndpointHandle(rendered.edges[0].targetHandle)).toEqual({
      kind: 'workflow-input', id: 'image-port',
    })
  })
})
