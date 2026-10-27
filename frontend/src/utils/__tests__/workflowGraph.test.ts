import { describe, expect, it } from 'vitest'
import type { ToolMetadata, ToolNodeState } from '@/api/types'
import { emptyGraph, jsonDocumentsEqual } from '@/sessions/graphDocument'
import { decodeEndpointHandle } from '../endpointHandles'
import {
  graphStateToVueFlow,
  removeNodesFromWorkflowInterface,
} from '../workflowGraph'

const tool: ToolMetadata = {
  name: 'threshold',
  display_name: 'Threshold',
  package: 'example',
  package_version: '1',
  tool_type: 'ProcessingTool',
  accepts_upstream: true,
  dynamic_outputs: false,
  dataframe_output: true,
  row_consumption: 'mapped',
  source_kind: 'package',
  editable: false,
  documentation: '',
  tags: [],
  categories: [],
  inputs: { image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default' } },
  outputs: { mask: { type: 'MaskPath' } },
  environment: null,
}

describe('canonical JSON documents', () => {
  it('compares schema objects independently of key order', () => {
    expect(jsonDocumentsEqual(
      { type: 'array', items: { type: 'integer', minimum: 0 } },
      { items: { minimum: 0, type: 'integer' }, type: 'array' },
    )).toBe(true)
  })
})

describe('graphStateToVueFlow', () => {
  function boundGraph() {
    const graph = emptyGraph('root', 'Root')
    graph.nodes = [{
      type: 'tool', id: 'write', name: 'Write', tool_name: 'threshold',
      tool_module: 'owned.report', tool_class: 'Report',
      position: [0, 0], parameters: {}, enabled: true, collapsed: false,
      output_templates: { result: 'authored_{row_index}.txt' },
    }]
    return graph
  }

  it('resolves workflow hints with accepted scoped leaf metadata and refuses a missing explicit owner', () => {
    const leaf = boundGraph()
    leaf.interface.inputs.push({ id: 'image-port', name: 'Image', kind: 'field', schema: { type: 'ImageFile' }, default: null,
      targets: [{ node: 'write', port: { kind: 'field', name: 'image' } }],
    })
    const graph = emptyGraph('root', 'Root')
    graph.nodes.push({ type: 'workflow', id: 'child', name: 'Child', workflow: leaf, position: [0, 0], bindings: {}, enabled: true, collapsed: false })
    const scopes: string[] = []
    const rendered = graphStateToVueFlow(graph, () => tool, [], (_node, scopedId) => { scopes.push(scopedId); return null })
    expect(scopes).toEqual(['child/write'])
    expect(rendered.nodes[0].data.workflowInputPresentation['image-port']).toMatchObject({ canPin: false, metadataAvailable: false, field: { display_name: 'Image' } })
    const accepted = graphStateToVueFlow(graph, () => undefined, [], (_node, scopedId) => scopedId === 'child/write' ? tool : null)
    expect(accepted.nodes[0].data.workflowInputPresentation['image-port']).toMatchObject({ canPin: true, metadataAvailable: true })
  })

  it('uses node-addressed Path metadata instead of a same-named catalog tool', () => {
    const graph = boundGraph()
    const scoped: ToolMetadata = {
      ...tool,
      inputs: {}, outputs: { result: { type: 'Path', default: 'default_{row_index}.txt' } },
    }
    const rendered = graphStateToVueFlow(graph, () => tool, [{
      node_id: 'write', tool_name: 'threshold', installed_versions: [],
    }], node => node.id === 'write' ? scoped : undefined)

    expect(rendered.nodes[0].data.tool).toEqual(scoped)
    expect(rendered.nodes[0].data.missingTool).toBeNull()
    expect(rendered.nodes[0].data.output_templates).toEqual({ result: 'authored_{row_index}.txt' })
    expect(rendered.nodes[0].data.pinnedInputs).toEqual({})
  })

  it('does not rescue an explicitly unavailable scoped binding from the catalog', () => {
    const graph = boundGraph()
    const before = JSON.parse(JSON.stringify(graph))
    const missing = { node_id: 'write', tool_name: 'threshold', installed_versions: [] }
    const rendered = graphStateToVueFlow(graph, () => tool, [missing], () => null)

    expect(rendered.nodes[0].data.tool).toBeNull()
    expect(rendered.nodes[0].data.missingTool).toEqual(missing)
    expect(rendered.nodes[0].data.output_templates).toEqual({ result: 'authored_{row_index}.txt' })
    expect(rendered.nodes[0].data.toolModule).toBe('owned.report')
    expect(rendered.nodes[0].data.toolClass).toBe('Report')
    expect(graph).toEqual(before)
  })

  it('retains catalog fallback for an unbound node with no scoped metadata', () => {
    const graph = boundGraph()
    const node = graph.nodes[0] as ToolNodeState
    delete node.tool_module
    delete node.tool_class
    node.output_templates = { mask: 'mask_{row_index}.tif' }
    const rendered = graphStateToVueFlow(graph, () => tool, [], () => undefined)

    expect(rendered.nodes[0].data.tool).toEqual(tool)
    expect(rendered.nodes[0].data.output_templates).toEqual({ mask: 'mask_{row_index}.tif' })
    expect(rendered.nodes[0].data.pinnedInputs).toEqual({ image: true })
  })

  it('preserves carried templates and binding while scoped metadata is unavailable', () => {
    const graph = emptyGraph('root', 'Root')
    graph.nodes = [{
      type: 'tool', id: 'write', name: 'Write', tool_name: 'TemplateReport',
      tool_module: 'platform_template_test_tools', tool_class: 'TemplateReport',
      position: [0, 0], parameters: {}, enabled: true, collapsed: false,
      output_templates: { result: 'authored_{row_index}.txt' },
    }]
    const before = JSON.parse(JSON.stringify(graph))

    const rendered = graphStateToVueFlow(graph, () => undefined)

    expect(rendered.nodes[0].data.tool).toBeNull()
    expect(rendered.nodes[0].data.output_templates).toEqual({
      result: 'authored_{row_index}.txt',
    })
    expect(rendered.nodes[0].data.toolModule).toBe('platform_template_test_tools')
    expect(rendered.nodes[0].data.toolClass).toBe('TemplateReport')
    expect(graph).toEqual(before)
  })

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

describe('removeNodesFromWorkflowInterface', () => {
  it('removes outputs and input targets owned by deleted nodes', () => {
    const workflowInterface = {
      inputs: [
        {
          id: 'shared-input',
          name: 'Shared input',
          kind: 'field' as const,
          schema: { type: 'int' },
          default: null,
          targets: [
            { node: 'deleted', port: { kind: 'field' as const, name: 'value' } },
            { node: 'surviving', port: { kind: 'field' as const, name: 'value' } },
          ],
        },
        {
          id: 'deleted-input',
          name: 'Deleted input',
          kind: 'field' as const,
          schema: { type: 'int' },
          default: null,
          targets: [
            { node: 'deleted', port: { kind: 'field' as const, name: 'other' } },
          ],
        },
      ],
      outputs: [
        {
          id: 'deleted-output',
          name: 'Deleted output',
          schema: { type: 'int' },
          source: { node: 'deleted', column: 'result' },
        },
        {
          id: 'surviving-output',
          name: 'Surviving output',
          schema: { type: 'int' },
          source: { node: 'surviving', column: 'result' },
        },
      ],
    }

    const result = removeNodesFromWorkflowInterface(
      workflowInterface,
      new Set(['deleted']),
    )

    expect(result.inputs).toEqual([{
      ...workflowInterface.inputs[0],
      targets: [workflowInterface.inputs[0].targets[1]],
    }])
    expect(result.outputs).toEqual([workflowInterface.outputs[1]])
    expect(workflowInterface.inputs).toHaveLength(2)
    expect(workflowInterface.outputs).toHaveLength(2)
  })
})
